#pragma once

#include "types.hpp"

#include <cstddef>
#include <vector>

namespace real_ids {

class EthRingBuffer {
 public:
  explicit EthRingBuffer(std::size_t capacity);

  void push(const EthernetPacket& item);

  /// Packets with timestamp in [start_ms, end_ms] inclusive.
  std::vector<EthernetPacket> items_within_timeframe(std::uint64_t start_ms,
                                                      std::uint64_t end_ms) const;

 private:
  std::vector<EthernetPacket> buffer_;
  std::size_t capacity_{0};
  std::size_t head_{0};
  std::size_t tail_{0};
  std::size_t count_{0};
};

}  // namespace real_ids
