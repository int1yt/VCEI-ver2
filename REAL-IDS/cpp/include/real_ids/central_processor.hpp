#pragma once

#include "eth_buffer.hpp"
#include "types.hpp"

#include <cstdint>
#include <string>

namespace real_ids {

/// Correlates CAN anomaly window with Ethernet ring buffer (fusion / classification).
class CentralProcessor {
 public:
  explicit CentralProcessor(EthRingBuffer* eth_buffer);

  Alert process_alert(const CanPacket& can_packet, std::uint64_t processor_time_ms,
                      bool production_mode);

 private:
  EthRingBuffer* eth_buffer_{nullptr};
  std::uint64_t alert_counter_{0};
};

}  // namespace real_ids
