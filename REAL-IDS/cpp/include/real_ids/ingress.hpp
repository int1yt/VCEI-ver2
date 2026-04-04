#pragma once

#include "types.hpp"

namespace real_ids {

/// Implement for SocketCAN / CAN-FD / vendor SDK.
class ICanIngress {
 public:
  virtual ~ICanIngress() = default;
  /// Non-blocking: return false if no frame available.
  virtual bool try_pop(CanPacket& out) = 0;
};

/// Implement for raw socket, AF_PACKET, or switch TAP mirroring.
class IEthIngress {
 public:
  virtual ~IEthIngress() = default;
  virtual bool try_pop(EthernetPacket& out) = 0;
};

}  // namespace real_ids
