#pragma once
#include "can_ids.hpp"
#include "eth_buffer.hpp"
#include <string>
#include <vector>

struct Alert {
    std::string id;
    uint64_t timestamp;
    CANPacket canPacket;
    std::vector<EthernetPacket> ethernetContext;
    std::string classification;
    float confidence;
};

class CentralProcessor {
public:
    CentralProcessor(EthRingBuffer* ethBuf) : ethBuffer(ethBuf), alertCounter(0) {}

    Alert processAlert(const CANPacket& canPacket, uint64_t currentTime) {
        // 提取告警前 500ms 到后 100ms 的以太网上下文
        uint64_t contextStartTime = (canPacket.timestamp > 500) ? (canPacket.timestamp - 500) : 0;
        uint64_t contextEndTime = canPacket.timestamp + 100;
        
        auto contextPackets = ethBuffer->getItemsWithinTimeframe(contextStartTime, contextEndTime);

        std::string classification = "Unknown";
        float confidence = 0.0f;

        bool hasEthernetAttack = false;
        for (const auto& p : contextPackets) {
            if (p.isAttack) {
                hasEthernetAttack = true;
                break;
            }
        }

        // 简单的机器学习分类逻辑模拟
        if (hasEthernetAttack && canPacket.isAttack) {
            classification = "Ethernet -> CAN (Cross-Domain Attack)";
            confidence = 0.95f;
        } else if (canPacket.isAttack) {
            classification = "Internal CAN Injection";
            confidence = 0.88f;
        } else {
            classification = "False Positive";
            confidence = 0.65f;
        }

        alertCounter++;
        Alert alert;
        alert.id = "ALT-" + std::to_string(alertCounter) + "-" + std::to_string(currentTime);
        alert.timestamp = currentTime;
        alert.canPacket = canPacket;
        alert.ethernetContext = contextPackets;
        alert.classification = classification;
        alert.confidence = confidence;

        return alert;
    }

private:
    EthRingBuffer* ethBuffer;
    uint32_t alertCounter;
};
