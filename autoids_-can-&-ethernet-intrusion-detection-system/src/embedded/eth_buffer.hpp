#pragma once
#include <stdint.h>
#include <vector>
#include <mutex>

struct EthernetPacket {
    uint32_t id;
    uint64_t timestamp; // gPTP timestamp
    uint32_t srcIp;
    uint32_t dstIp;
    uint16_t protocol;
    uint16_t length;
    bool isAttack; // 仅用于模拟标记
};

class EthRingBuffer {
public:
    EthRingBuffer(size_t cap) : capacity(cap), head(0), tail(0), count(0) {
        buffer.resize(capacity);
    }

    void push(const EthernetPacket& packet) {
        std::lock_guard<std::mutex> lock(mtx);
        buffer[head] = packet;
        head = (head + 1) % capacity;
        if (count < capacity) {
            count++;
        } else {
            tail = (tail + 1) % capacity;
        }
    }

    std::vector<EthernetPacket> getItemsWithinTimeframe(uint64_t startTime, uint64_t endTime) {
        std::lock_guard<std::mutex> lock(mtx);
        std::vector<EthernetPacket> items;
        size_t current = tail;
        for (size_t i = 0; i < count; i++) {
            const auto& item = buffer[current];
            if (item.timestamp >= startTime && item.timestamp <= endTime) {
                items.push_back(item);
            }
            current = (current + 1) % capacity;
        }
        return items;
    }

private:
    std::vector<EthernetPacket> buffer;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
    std::mutex mtx;
};
