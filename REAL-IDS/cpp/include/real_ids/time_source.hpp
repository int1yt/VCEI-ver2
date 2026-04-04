#pragma once

#include <chrono>
#include <cstdint>

namespace real_ids {

/// Pluggable time; replace with gPTP-backed implementation on-vehicle.
class TimeSource {
 public:
  virtual ~TimeSource() = default;
  virtual std::uint64_t now_ms() const = 0;
};

class SystemTimeSource final : public TimeSource {
 public:
  std::uint64_t now_ms() const override {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
  }
};

}  // namespace real_ids
