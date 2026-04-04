#include "real_ids/engine.hpp"

#include <optional>

namespace real_ids {

IdsEngine::IdsEngine(std::unique_ptr<TimeSource> clock, std::size_t eth_capacity, EngineMode mode)
    : clock_(std::move(clock)),
      eth_buffer_(eth_capacity),
      can_ids_(),
      central_(&eth_buffer_),
      mode_(mode) {}

void IdsEngine::set_callbacks(EngineCallbacks cb) {
  std::lock_guard<std::mutex> lock(cb_mu_);
  callbacks_ = std::move(cb);
}

void IdsEngine::clear_callbacks() {
  std::lock_guard<std::mutex> lock(cb_mu_);
  callbacks_ = {};
}

void IdsEngine::train(const CanPacket& packet) {
  std::lock_guard<std::mutex> lock(engine_mu_);
  can_ids_.train(packet);
}

void IdsEngine::ingest_can(CanPacket packet) {
  EngineCallbacks local;
  {
    std::lock_guard<std::mutex> lock(cb_mu_);
    local = callbacks_;
  }

  if (local.on_can_packet) {
    local.on_can_packet(packet);
  }

  std::optional<Alert> emitted;
  {
    std::lock_guard<std::mutex> lock(engine_mu_);

    if (training_) {
      can_ids_.train(packet);
    } else {
      const bool anomaly = can_ids_.detect(packet);

      bool fire = false;
      if (mode_ == EngineMode::SimulationParity) {
        fire = anomaly && packet.synthetic_attack_flag;
      } else {
        fire = anomaly;
      }

      if (fire) {
        if (alert_cooldown_ticks_ > 0) {
          --alert_cooldown_ticks_;
        } else {
          const auto t = clock_->now_ms();
          emitted = central_.process_alert(packet, t, mode_ == EngineMode::Production);
          alert_cooldown_ticks_ = alert_cooldown_ticks_max_;
        }
      } else if (alert_cooldown_ticks_ > 0) {
        --alert_cooldown_ticks_;
      }
    }
  }

  if (emitted && local.on_alert) {
    local.on_alert(*emitted);
  }
}

void IdsEngine::ingest_eth(const EthernetPacket& packet) {
  {
    std::lock_guard<std::mutex> lock(engine_mu_);
    eth_buffer_.push(packet);
  }
  EngineCallbacks local;
  {
    std::lock_guard<std::mutex> lock(cb_mu_);
    local = callbacks_;
  }
  if (local.on_eth_packet) {
    local.on_eth_packet(packet);
  }
}

}  // namespace real_ids
