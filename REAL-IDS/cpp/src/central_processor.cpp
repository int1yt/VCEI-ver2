#include "real_ids/central_processor.hpp"

namespace real_ids {

CentralProcessor::CentralProcessor(EthRingBuffer* eth_buffer) : eth_buffer_(eth_buffer) {}

Alert CentralProcessor::process_alert(const CanPacket& can_packet, std::uint64_t processor_time_ms,
                                        bool production_mode) {
  const std::uint64_t context_start =
      can_packet.timestamp_ms > 500 ? (can_packet.timestamp_ms - 500) : 0;
  const std::uint64_t context_end = can_packet.timestamp_ms + 100;

  auto context = eth_buffer_->items_within_timeframe(context_start, context_end);

  bool has_eth_attack = false;
  for (const auto& p : context) {
    if (p.synthetic_attack_flag) {
      has_eth_attack = true;
      break;
    }
  }

  std::string classification = "Unknown";
  float confidence = 0.F;

  if (production_mode) {
    classification = has_eth_attack ? "CAN anomaly with suspicious ETH context"
                                    : "CAN timing anomaly (" + can_packet.id + ")";
    confidence = has_eth_attack ? 0.82F : 0.78F;
  } else if (has_eth_attack && can_packet.synthetic_attack_flag) {
    classification = "Ethernet -> CAN (" + can_packet.id + ")";
    confidence = 0.92F;
  } else if (can_packet.synthetic_attack_flag) {
    classification = "Internal CAN (" + can_packet.id + ")";
    confidence = 0.85F;
  } else {
    classification = "Anomaly (no attack metadata)";
    confidence = 0.75F;
  }

  ++alert_counter_;
  Alert alert;
  alert.id = "ALT-" + std::to_string(alert_counter_) + "-" + std::to_string(processor_time_ms);
  alert.timestamp_ms = processor_time_ms;
  alert.can_packet = can_packet;
  alert.ethernet_context = std::move(context);
  alert.classification = std::move(classification);
  alert.confidence = confidence;
  return alert;
}

}  // namespace real_ids
