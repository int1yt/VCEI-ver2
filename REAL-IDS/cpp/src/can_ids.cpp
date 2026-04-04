#include "real_ids/can_ids.hpp"

#include <cmath>

namespace real_ids {

CanClockSkewIds::CanClockSkewIds(double skew_threshold_ms) : skew_threshold_ms_(skew_threshold_ms) {}

void CanClockSkewIds::train(const CanPacket& packet) {
  auto it = baselines_.find(packet.id);
  if (it == baselines_.end()) {
    baselines_.emplace(packet.id, BaselineState{0.0, packet.timestamp_ms});
    return;
  }
  auto& state = it->second;
  if (state.interval_ms == 0.0) {
    state.interval_ms = static_cast<double>(packet.timestamp_ms - state.last_seen_ms);
  } else {
    const double delta = static_cast<double>(packet.timestamp_ms - state.last_seen_ms);
    state.interval_ms = state.interval_ms * 0.9 + delta * 0.1;
  }
  state.last_seen_ms = packet.timestamp_ms;
}

bool CanClockSkewIds::detect(CanPacket& packet) {
  auto it = baselines_.find(packet.id);
  if (it == baselines_.end()) return false;

  auto& state = it->second;
  const double expected =
      static_cast<double>(state.last_seen_ms) + (state.interval_ms > 0.0 ? state.interval_ms : 0.0);
  const double skew = std::abs(static_cast<double>(packet.timestamp_ms) - expected);

  state.last_seen_ms = packet.timestamp_ms;

  return skew > skew_threshold_ms_;
}

}  // namespace real_ids
