#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace real_ids {

struct CanPacket {
  std::string id;
  std::uint64_t timestamp_ms{0};
  std::string data_hex;
  bool synthetic_attack_flag{false};
};

struct EthernetPacket {
  std::string id;
  std::uint64_t timestamp_ms{0};
  std::string src_ip;
  std::string dst_ip;
  std::string protocol;
  std::uint32_t length{0};
  bool synthetic_attack_flag{false};
};

struct Alert {
  std::string id;
  std::uint64_t timestamp_ms{0};
  CanPacket can_packet;
  std::vector<EthernetPacket> ethernet_context;
  std::string classification;
  float confidence{0.F};
};

}  // namespace real_ids
