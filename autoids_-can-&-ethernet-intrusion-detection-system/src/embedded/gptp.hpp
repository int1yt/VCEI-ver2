#pragma once
#include <stdint.h>
#include <chrono>

namespace gPTP {
    // 模拟 gPTP (IEEE 802.1AS) 获取全局同步时间戳
    // 在真实车机中，这里会调用硬件时间戳寄存器或 PTP 协议栈接口
    inline uint64_t get_global_time_ms() {
        auto now = std::chrono::system_clock::now();
        auto duration = now.time_since_epoch();
        return std::chrono::duration_cast<std::chrono::milliseconds>(duration).count();
    }
}
