// ============================================================
//  clock_time.h — 系统时间（NTP 同步 + BLE 手动校准 + 本地时区）
// ============================================================
#pragma once

#include <stdint.h>

namespace ClockT {

void begin();            // 启动 NTP（CST-8，国内两个源互备）
void loop();

// 当前 Unix 时间戳；epochValid=false 说明还没同步过，显示应给"同步中"提示
uint32_t epoch();
bool     valid();

// BLE / 串口手动设置时间（秒）
void setEpoch(uint32_t e);

}  // namespace ClockT
