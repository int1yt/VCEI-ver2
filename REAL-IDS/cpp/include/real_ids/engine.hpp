#pragma once

#include "can_ids.hpp"
#include "central_processor.hpp"
#include "eth_buffer.hpp"
#include "time_source.hpp"
#include "types.hpp"

#include <functional>
#include <memory>
#include <mutex>
#include <optional>
#include <string>

namespace real_ids {

enum class EngineMode {
  /// Matches autoids server.ts: alert only if IDS detects skew AND frame carries synthetic_attack_flag.
  SimulationParity,
  /// Deployable: alert on CAN timing anomaly; fusion uses eth buffer only as context (no synthetic flags required).
  Production,
};

struct EngineCallbacks {
  std::function<void(const CanPacket&)> on_can_packet;
  std::function<void(const EthernetPacket&)> on_eth_packet;
  std::function<void(const Alert&)> on_alert;
};

/// Thread-safe façade around buffer + IDS + fusion (single-writer recommended for training).
class IdsEngine {
 public:
  IdsEngine(std::unique_ptr<TimeSource> clock, std::size_t eth_capacity, EngineMode mode);

  void set_mode(EngineMode m) { mode_ = m; }
  EngineMode mode() const { return mode_; }

  void set_callbacks(EngineCallbacks cb);
  void clear_callbacks();

  /// Pre-train baselines (call before switching to detect).
  void train(const CanPacket& packet);

  void finish_training() { training_ = false; }
  void start_training() { training_ = true; }
  bool is_training() const { return training_; }

  /// Ingest one CAN frame: updates IDS, may emit alert via callback.
  void ingest_can(CanPacket packet);

  /// Ingest one Ethernet frame into ring buffer and notify subscribers.
  void ingest_eth(const EthernetPacket& packet);

  void reset_alert_cooldown_ticks() { alert_cooldown_ticks_ = 0; }
  void set_alert_cooldown_ticks(int ticks) { alert_cooldown_ticks_max_ = ticks; }

  std::uint64_t now_ms() const { return clock_->now_ms(); }

 private:
  std::unique_ptr<TimeSource> clock_;
  EthRingBuffer eth_buffer_;
  CanClockSkewIds can_ids_;
  CentralProcessor central_;
  EngineMode mode_;
  bool training_{true};
  EngineCallbacks callbacks_;
  mutable std::mutex cb_mu_;

  int alert_cooldown_ticks_{0};
  int alert_cooldown_ticks_max_{100};

  /// Serializes CAN IDS + ring buffer updates (producer threads must not interleave).
  mutable std::mutex engine_mu_;
};

}  // namespace real_ids
