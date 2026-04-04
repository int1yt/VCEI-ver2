export interface CANPacket {
  id: string;
  timestamp: number;
  data: string;
  isAttack: boolean;
}

export interface EthernetPacket {
  id: string;
  timestamp: number;
  srcIp: string;
  dstIp: string;
  protocol: string;
  length: number;
  isAttack: boolean;
}

export interface Alert {
  id: string;
  timestamp: number;
  canPacket: CANPacket;
  ethernetContext: EthernetPacket[];
  classification: string;
  confidence: number;
}
