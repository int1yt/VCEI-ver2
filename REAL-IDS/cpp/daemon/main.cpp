// real_ids_daemon — HTTP API + SSE for IDS dashboard; simulation mode matches autoids server.ts.

#define CPPHTTPLIB_LISTEN_BACKLOG 256
#include <httplib.h>
#include <nlohmann/json.hpp>

#include "broadcast_hub.hpp"
#include "real_ids/engine.hpp"
#include "real_ids/time_source.hpp"

#include <atomic>
#include <chrono>
#include <cctype>
#include <cstring>
#include <cstdlib>
#include <deque>
#include <memory>
#include <mutex>
#include <random>
#include <sstream>
#include <string>
#include <thread>

namespace {

using json = nlohmann::json;
using namespace real_ids;
using namespace real_ids::daemon;

std::shared_ptr<IdsEngine> g_engine;
std::mutex g_engine_mu;

BroadcastHub g_hub;

std::atomic<bool> g_sim_running{false};
std::atomic<int> g_pending_can{0};
std::atomic<int> g_pending_eth{0};

std::mt19937 g_rng{std::random_device{}()};

std::deque<CanPacket> g_can_hist;
std::mutex g_can_hist_mu;
constexpr std::size_t k_can_hist_cap = 29;

std::string random_hex8() {
  std::uniform_int_distribution<unsigned> dist(0, 0xFFFFFFFFu);
  std::ostringstream oss;
  oss << std::hex << std::uppercase << dist(g_rng);
  std::string s = oss.str();
  if (s.size() < 8) s.insert(s.begin(), 8 - s.size(), '0');
  if (s.size() > 8) s = s.substr(s.size() - 8);
  return s;
}

json can_json(const CanPacket& p) {
  return json{{"id", p.id},
              {"timestamp", p.timestamp_ms},
              {"data", p.data_hex},
              {"isAttack", p.synthetic_attack_flag}};
}

json eth_json(const EthernetPacket& p) {
  return json{{"id", p.id},
              {"timestamp", p.timestamp_ms},
              {"srcIp", p.src_ip},
              {"dstIp", p.dst_ip},
              {"protocol", p.protocol},
              {"length", p.length},
              {"isAttack", p.synthetic_attack_flag}};
}

json alert_json(const Alert& a) {
  json eth_ctx = json::array();
  for (const auto& e : a.ethernet_context) {
    eth_ctx.push_back(eth_json(e));
  }
  return json{{"id", a.id},
              {"timestamp", a.timestamp_ms},
              {"canPacket", can_json(a.can_packet)},
              {"ethernetContext", std::move(eth_ctx)},
              {"classification", a.classification},
              {"confidence", a.confidence}};
}

void append_can_history(const CanPacket& p) {
  std::lock_guard<std::mutex> lk(g_can_hist_mu);
  g_can_hist.push_back(p);
  while (g_can_hist.size() > k_can_hist_cap) {
    g_can_hist.pop_front();
  }
}

void try_ml_bridge_enrich(const Alert& a, json& payload) {
  const char* base = std::getenv("REAL_IDS_ML_BRIDGE");
  if (!base || !base[0]) return;

  json body;
  body["real_ids_classification"] = a.classification;
  body["can_skew_triggered"] = true;
  body["trigger_can"] = can_json(a.can_packet);

  json eth_arr = json::array();
  for (const auto& e : a.ethernet_context) {
    eth_arr.push_back(eth_json(e));
  }
  body["ethernet_context"] = std::move(eth_arr);

  json hist = json::array();
  {
    std::lock_guard<std::mutex> lk(g_can_hist_mu);
    for (const auto& c : g_can_hist) {
      hist.push_back(can_json(c));
    }
  }
  body["can_history"] = std::move(hist);

  httplib::Client cli(base);
  cli.set_connection_timeout(0, 800000);
  cli.set_read_timeout(8, 0);
  auto res = cli.Post("/v1/enrich", body.dump(), "application/json");
  if (!res) {
    std::fprintf(stderr, "[REAL-IDS] ml_bridge: POST /v1/enrich failed: %s (REAL_IDS_ML_BRIDGE=%s)\n",
                 httplib::to_string(res.error()).c_str(), base);
    std::fprintf(stderr, "[REAL-IDS] Is uvicorn running? Try: curl %s/health\n", base);
    return;
  }
  if (res->status != 200) {
    std::fprintf(stderr, "[REAL-IDS] ml_bridge: HTTP %d (expected 200). Body: %.200s\n", res->status,
                 res->body.c_str());
    return;
  }
  try {
    payload["ml_fusion"] = json::parse(res->body);
  } catch (...) {
    std::fprintf(stderr, "[REAL-IDS] ml_bridge: invalid JSON in response\n");
  }
}

void publish(const json& j) {
  g_hub.publish(j.dump());
}

void cors(httplib::Response& res) {
  res.set_header("Access-Control-Allow-Origin", "*");
  res.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.set_header("Access-Control-Allow-Headers", "Content-Type");
}

void pretrain_engine(IdsEngine& engine) {
  const std::string ids[] = {"0x1A4", "0x2B0", "0x3C1"};
  std::uint64_t train_time = engine.now_ms() - 10000;
  for (int i = 0; i < 100; ++i) {
    for (const auto& id : ids) {
      CanPacket p;
      p.id = id;
      p.timestamp_ms = train_time;
      p.data_hex = "00000000";
      p.synthetic_attack_flag = false;
      engine.train(p);
    }
    train_time += 20;
  }
  engine.finish_training();
}

void can_sim_thread() {
  const std::string k_ids[] = {"0x1A4", "0x2B0", "0x3C1"};
  constexpr auto period = std::chrono::milliseconds(20);

  while (true) {
    std::this_thread::sleep_for(period);
    if (!g_sim_running.load()) continue;

    std::shared_ptr<IdsEngine> eng;
    {
      std::lock_guard<std::mutex> lock(g_engine_mu);
      eng = g_engine;
    }
    if (!eng) continue;

    const std::uint64_t now = eng->now_ms();

    for (const auto& id : k_ids) {
      CanPacket packet;
      packet.id = id;
      packet.timestamp_ms = now;
      packet.data_hex = random_hex8();
      packet.synthetic_attack_flag = false;

      int pending = g_pending_can.load();
      if (pending > 0 && id == "0x1A4") {
        packet.synthetic_attack_flag = true;
        packet.timestamp_ms = now - 50;
        g_pending_can.fetch_sub(1);
      }

      eng->ingest_can(std::move(packet));
    }
  }
}

void eth_sim_thread() {
  const char* normal_ips[] = {"10.0.0.5",  "10.0.0.12", "10.0.0.45",
                              "10.0.0.104", "10.0.0.222", "10.0.1.15", "10.0.1.50"};
  constexpr auto period = std::chrono::milliseconds(10);

  while (true) {
    std::this_thread::sleep_for(period);
    if (!g_sim_running.load()) continue;

    std::shared_ptr<IdsEngine> eng;
    {
      std::lock_guard<std::mutex> lock(g_engine_mu);
      eng = g_engine;
    }
    if (!eng) continue;

    EthernetPacket eth;
    eth.timestamp_ms = eng->now_ms();
    eth.id = "ETH-" + std::to_string(g_rng() % 100000);
    eth.dst_ip = "10.0.0.1";
    eth.length = static_cast<std::uint32_t>((g_rng() % 1000) + 64);
    eth.synthetic_attack_flag = false;

    int peth = g_pending_eth.load();
    if (peth > 0) {
      eth.synthetic_attack_flag = true;
      eth.src_ip = "192.168.1.100";
      eth.protocol = "TCP";
      g_pending_eth.fetch_sub(1);
    } else {
      eth.src_ip = normal_ips[g_rng() % 7];
      eth.protocol = "UDP";
    }

    eng->ingest_eth(eth);
  }
}

EngineMode mode_from_env() {
  const char* m = std::getenv("REAL_IDS_MODE");
  if (m && std::string(m) == "production") {
    return EngineMode::Production;
  }
  return EngineMode::SimulationParity;
}

int port_from_env() {
  const char* p = std::getenv("REAL_IDS_PORT");
  if (p && *p) {
    return std::atoi(p);
  }
  return 8080;
}

}  // namespace

int main() {
  auto engine = std::make_shared<IdsEngine>(std::make_unique<SystemTimeSource>(), 1000, mode_from_env());
  pretrain_engine(*engine);

  EngineCallbacks cb;
  cb.on_can_packet = [](const CanPacket& p) {
    append_can_history(p);
    publish(json{{"event", "can-packet"}, {"payload", can_json(p)}});
  };
  cb.on_eth_packet = [](const EthernetPacket& p) {
    publish(json{{"event", "eth-packet"}, {"payload", eth_json(p)}});
  };
  cb.on_alert = [](const Alert& a) {
    json payload = alert_json(a);
    try_ml_bridge_enrich(a, payload);
    publish(json{{"event", "alert"}, {"payload", std::move(payload)}});
  };
  engine->set_callbacks(std::move(cb));
  engine->set_alert_cooldown_ticks(100);

  {
    std::lock_guard<std::mutex> lock(g_engine_mu);
    g_engine = engine;
  }

  std::thread(can_sim_thread).detach();
  std::thread(eth_sim_thread).detach();

  httplib::Server svr;

  svr.set_pre_routing_handler([](const httplib::Request& req, httplib::Response& res) {
    cors(res);
    if (req.method == "OPTIONS") {
      res.status = 204;
      return httplib::Server::HandlerResponse::Handled;
    }
    return httplib::Server::HandlerResponse::Unhandled;
  });

  svr.Get("/api/health", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(json{{"status", "ok"}}.dump(), "application/json");
  });

  svr.Get("/api/v1/health", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(json{{"status", "ok"}, {"service", "real-ids"}}.dump(), "application/json");
  });

  svr.Get("/api/stats", [](const httplib::Request&, httplib::Response& res) {
    json body = {{"baselineAccuracy", 0.98}, {"recognitionAccuracy", 0.95}, {"averageLatency", 12.5}};
    res.set_content(body.dump(), "application/json");
  });

  svr.Get("/api/v1/stats", [](const httplib::Request&, httplib::Response& res) {
    json body = {{"baselineAccuracy", 0.98},
                 {"recognitionAccuracy", 0.95},
                 {"averageLatency", 12.5},
                 {"subscribers", g_hub.subscriber_count()}};
    res.set_content(body.dump(), "application/json");
  });

  svr.Post("/api/simulation/start", [](const httplib::Request&, httplib::Response& res) {
    g_sim_running = true;
    publish(json{{"event", "status"}, {"payload", json{{"running", true}}}});
    res.set_content(json{{"status", "started"}}.dump(), "application/json");
  });

  svr.Post("/api/simulation/stop", [](const httplib::Request&, httplib::Response& res) {
    g_sim_running = false;
    g_pending_can = 0;
    g_pending_eth = 0;
    publish(json{{"event", "status"}, {"payload", json{{"running", false}}}});
    res.set_content(json{{"status", "stopped"}}.dump(), "application/json");
  });

  svr.Post("/api/simulation/attack", [](const httplib::Request& req, httplib::Response& res) {
    json body = json::object();
    if (!req.body.empty()) {
      try {
        body = json::parse(req.body);
      } catch (...) {
        res.status = 400;
        res.set_content(json{{"error", "invalid JSON"}}.dump(), "application/json");
        return;
      }
    }
    std::string type = body.value("type", "ethernet-can");

    if (type == "ethernet-can") {
      g_pending_eth += 15;
      std::thread([] {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        g_pending_can += 8;
      }).detach();
    } else {
      g_pending_can += 8;
    }

    publish(json{{"event", "attack_launched"}, {"payload", json{{"type", type}}}});
    res.set_content(json{{"status", "attack_launched"}, {"type", type}}.dump(), "application/json");
  });

  // Mirror paths for /api/v1/* (recommended for new dashboards)
  svr.Post("/api/v1/simulation/start", [](const httplib::Request&, httplib::Response& res) {
    g_sim_running = true;
    publish(json{{"event", "status"}, {"payload", json{{"running", true}}}});
    res.set_content(json{{"status", "started"}}.dump(), "application/json");
  });
  svr.Post("/api/v1/simulation/stop", [](const httplib::Request&, httplib::Response& res) {
    g_sim_running = false;
    g_pending_can = 0;
    g_pending_eth = 0;
    publish(json{{"event", "status"}, {"payload", json{{"running", false}}}});
    res.set_content(json{{"status", "stopped"}}.dump(), "application/json");
  });
  svr.Post("/api/v1/simulation/attack", [](const httplib::Request& req, httplib::Response& res) {
    json body = json::object();
    if (!req.body.empty()) {
      try {
        body = json::parse(req.body);
      } catch (...) {
        res.status = 400;
        res.set_content(json{{"error", "invalid JSON"}}.dump(), "application/json");
        return;
      }
    }
    std::string type = body.value("type", "ethernet-can");
    if (type == "ethernet-can") {
      g_pending_eth += 15;
      std::thread([] {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
        g_pending_can += 8;
      }).detach();
    } else {
      g_pending_can += 8;
    }
    publish(json{{"event", "attack_launched"}, {"payload", json{{"type", type}}}});
    res.set_content(json{{"status", "attack_launched"}, {"type", type}}.dump(), "application/json");
  });

  svr.Get("/api/v1/stream", [](const httplib::Request&, httplib::Response& res) {
    res.set_header("Cache-Control", "no-cache");
    res.set_header("Connection", "keep-alive");
    auto sub = g_hub.subscribe();

    res.set_chunked_content_provider(
        "text/event-stream",
        [sub](size_t /*offset*/, httplib::DataSink& sink) mutable -> bool {
          std::string line;
          if (!sub->pop_line(line, std::chrono::seconds(25))) {
            const char* ping = ": keepalive\n\n";
            return sink.write(ping, strlen(ping));
          }
          std::string block = "data: ";
          block += line;
          block += "\n\n";
          return sink.write(block.data(), block.size());
        },
        [sub](bool /*success*/) { g_hub.unsubscribe(sub); });
  });

  const int port = port_from_env();
  std::fprintf(stderr, "real_ids_daemon listening on 0.0.0.0:%d (SSE /api/v1/stream)\n", port);
  if (const char* bridge = std::getenv("REAL_IDS_ML_BRIDGE"); bridge && bridge[0]) {
    std::fprintf(stderr, "REAL_IDS_ML_BRIDGE=%s (enrich alerts via POST /v1/enrich)\n", bridge);
  } else {
    std::fprintf(stderr, "REAL_IDS_ML_BRIDGE not set — alerts have no ml_fusion. "
                         "Start ml_bridge then set e.g. http://127.0.0.1:5055 and restart daemon.\n");
  }
  svr.listen("0.0.0.0", port);
  return 0;
}
