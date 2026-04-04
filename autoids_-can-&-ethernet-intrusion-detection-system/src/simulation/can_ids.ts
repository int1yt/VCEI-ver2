import { CANPacket } from './types.js';

export class CANClockSkewIDS {
  private baselines: Map<string, { interval: number, lastSeen: number }> = new Map();
  private skewThreshold = 15; // ms (Increased to handle Node.js timer jitter)

  train(packet: CANPacket) {
    if (!this.baselines.has(packet.id)) {
      this.baselines.set(packet.id, { interval: 0, lastSeen: packet.timestamp });
    } else {
      const state = this.baselines.get(packet.id)!;
      if (state.interval === 0) {
        state.interval = packet.timestamp - state.lastSeen;
      } else {
        // Moving average for interval
        state.interval = state.interval * 0.9 + (packet.timestamp - state.lastSeen) * 0.1;
      }
      state.lastSeen = packet.timestamp;
    }
  }

  detect(packet: CANPacket): boolean {
    if (!this.baselines.has(packet.id)) return false;
    
    const state = this.baselines.get(packet.id)!;
    const expectedTime = state.lastSeen + state.interval;
    const skew = Math.abs(packet.timestamp - expectedTime);
    
    state.lastSeen = packet.timestamp; // Update last seen anyway

    return skew > this.skewThreshold;
  }
}
