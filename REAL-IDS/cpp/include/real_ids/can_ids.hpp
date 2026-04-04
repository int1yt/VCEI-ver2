#pragma once

#include "types.hpp"

#include <cstdint>
#include <string>
#include <unordered_map>

namespace real_ids {

/// Per-CAN-ID inter-arrival baseline with clock-skew anomaly detection (same idea as autoids).
class CanClockSkewIds {
 public:
  explicit CanClockSkewIds(double skew_threshold_ms = 15.0);

  void train(const CanPacket& packet);
  /// Returns true if arrival deviates from learned interval beyond threshold.
  bool detect(CanPacket& packet);

  void set_skew_threshold_ms(double ms) { skew_threshold_ms_ = ms; }

 private:
  struct BaselineState {
    double interval_ms{0.0};
    std::uint64_t last_seen_ms{0};
  };

  std::unordered_map<std::string, BaselineState> baselines_;
  double skew_threshold_ms_;
};

}  // namespace real_ids
