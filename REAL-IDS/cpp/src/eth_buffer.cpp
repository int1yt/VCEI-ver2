#include "real_ids/eth_buffer.hpp"

namespace real_ids {

EthRingBuffer::EthRingBuffer(std::size_t capacity) : capacity_(capacity) {
  buffer_.resize(capacity);
}

void EthRingBuffer::push(const EthernetPacket& item) {
  if (capacity_ == 0) return;
  buffer_[head_] = item;
  head_ = (head_ + 1) % capacity_;
  if (count_ < capacity_) {
    ++count_;
  } else {
    tail_ = (tail_ + 1) % capacity_;
  }
}

std::vector<EthernetPacket> EthRingBuffer::items_within_timeframe(std::uint64_t start_ms,
                                                                  std::uint64_t end_ms) const {
  std::vector<EthernetPacket> out;
  if (count_ == 0) return out;
  std::size_t current = tail_;
  for (std::size_t i = 0; i < count_; ++i) {
    const auto& item = buffer_[current];
    if (item.timestamp_ms >= start_ms && item.timestamp_ms <= end_ms) {
      out.push_back(item);
    }
    current = (current + 1) % capacity_;
  }
  return out;
}

}  // namespace real_ids
