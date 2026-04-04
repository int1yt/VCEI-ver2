import { CANPacket, EthernetPacket, Alert } from './types.js';
import { EthRingBuffer } from './eth_buffer.js';
import { gPTP } from './gptp.js';

export class CentralProcessor {
  private ethBuffer: EthRingBuffer;
  private alertCounter: number = 0;

  constructor(ethBuffer: EthRingBuffer) {
    this.ethBuffer = ethBuffer;
  }

  processAlert(canPacket: CANPacket): Alert {
    // Get context from Ethernet buffer (e.g., last 500ms)
    const contextStartTime = canPacket.timestamp - 500;
    const contextEndTime = canPacket.timestamp + 100;
    const contextPackets = this.ethBuffer.getItemsWithinTimeframe(contextStartTime, contextEndTime);

    // Simulate ML Classification
    let classification = "Unknown";
    let confidence = 0.0;

    const hasEthernetAttack = contextPackets.some(p => p.isAttack);

    if (hasEthernetAttack && canPacket.isAttack) {
      classification = `Ethernet -> CAN (${canPacket.id})`;
      confidence = 0.92 + Math.random() * 0.07;
    } else if (canPacket.isAttack) {
      classification = `Internal CAN (${canPacket.id})`;
      confidence = 0.85 + Math.random() * 0.1;
    } else {
      classification = "False Positive";
      confidence = 0.6 + Math.random() * 0.2;
    }

    this.alertCounter++;
    const currentTime = gPTP.getGlobalTimeMs();
    
    const alert: Alert = {
      id: `ALT-${this.alertCounter}-${currentTime}`,
      timestamp: currentTime,
      canPacket,
      ethernetContext: contextPackets,
      classification,
      confidence
    };

    return alert;
  }
}
