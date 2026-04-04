#pragma once
#include <stdint.h>
#include <unordered_map>
#include <cmath>

struct CANPacket {
    uint32_t id;
    uint64_t timestamp; // gPTP timestamp
    uint8_t data[8];
    bool isAttack; // 仅用于模拟标记
};

class CANClockSkewIDS {
public:
    CANClockSkewIDS(uint64_t threshold = 15) : skewThreshold(threshold) {}

    void train(const CANPacket& packet) {
        if (baselines.find(packet.id) == baselines.end()) {
            baselines[packet.id] = {0.0, packet.timestamp};
        } else {
            auto& state = baselines[packet.id];
            if (state.interval == 0.0) {
                state.interval = static_cast<double>(packet.timestamp - state.lastSeen);
            } else {
                // 指数移动平均 (EMA) 更新基线间隔
                state.interval = state.interval * 0.9 + static_cast<double>(packet.timestamp - state.lastSeen) * 0.1;
            }
            state.lastSeen = packet.timestamp;
        }
    }

    bool detect(const CANPacket& packet) {
        if (baselines.find(packet.id) == baselines.end()) return false;
        
        auto& state = baselines[packet.id];
        uint64_t expectedTime = state.lastSeen + static_cast<uint64_t>(state.interval);
        
        // 计算偏斜
        uint64_t skew = (packet.timestamp > expectedTime) ? 
                        (packet.timestamp - expectedTime) : 
                        (expectedTime - packet.timestamp);
        
        state.lastSeen = packet.timestamp; // 无论是否异常都更新最后一次看到的时间

        return skew > skewThreshold;
    }

private:
    struct State {
        double interval;
        uint64_t lastSeen;
    };
    std::unordered_map<uint32_t, State> baselines;
    uint64_t skewThreshold; // 毫秒
};
