import { EthernetPacket } from './types.js';

export class EthRingBuffer {
  private buffer: EthernetPacket[];
  private capacity: number;
  private head: number;
  private tail: number;
  private count: number;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.buffer = new Array(capacity);
    this.head = 0;
    this.tail = 0;
    this.count = 0;
  }

  push(item: EthernetPacket) {
    this.buffer[this.head] = item;
    this.head = (this.head + 1) % this.capacity;
    if (this.count < this.capacity) {
      this.count++;
    } else {
      this.tail = (this.tail + 1) % this.capacity;
    }
  }

  getItemsWithinTimeframe(startTime: number, endTime: number): EthernetPacket[] {
    const items: EthernetPacket[] = [];
    let current = this.tail;
    for (let i = 0; i < this.count; i++) {
      const item = this.buffer[current];
      if (item.timestamp >= startTime && item.timestamp <= endTime) {
        items.push(item);
      }
      current = (current + 1) % this.capacity;
    }
    return items;
  }
}
