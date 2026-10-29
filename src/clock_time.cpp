// ============================================================
//  clock_time.cpp — 系统时间
//  NTP 未同步前用 millis() 计时兜底（断电即丢，符合预期）；
//  同步成功后 epoch 以 NTP/RTC-free 方式由 lwip 时间函数维护。
// ============================================================
#include "clock_time.h"
#include "config.h"

#ifdef ARDUINO

#include <WiFi.h>
#include <time.h>

namespace ClockT {

namespace {
bool     gValid = false;
uint32_t gLastSyncMs = 0;
uint32_t gLastSyncEp = 0;
}

void begin() {
  // CST-8 固定偏移；夏令时不存在。阿里 + 国内 NTP pool 双源互备
  configTzTime("CST-8", "ntp.aliyun.com", "cn.pool.ntp.org", "pool.ntp.org");
  Serial.println("[TIME] ntp started (CST-8)");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) return;

  // 每 5 分钟校一次；首次同步检测 time() 有效性
  static uint32_t lastTry = 0;
  uint32_t now = millis();
  if (now - lastTry < 5000 && gValid && now - gLastSyncMs < 300000) return;
  lastTry = now;

  time_t t = time(nullptr);
  if (t > 1700000000) {                 // 2023 年后视为有效
    if (!gValid) {
      Serial.printf("[TIME] synced: %ld\n", (long)t);
    }
    gValid = true;
    gLastSyncMs = now;
    gLastSyncEp = (uint32_t)t;
  }
}

uint32_t epoch() {
  if (gValid) return (uint32_t)time(nullptr);
  // 未同步：从 0 起算的 millis/1000，表盘据此走"启动计时"兜底显示
  return millis() / 1000;
}

bool valid() { return gValid; }

void setEpoch(uint32_t e) {
  if (e < 1700000000) return;           // 拒绝野值
  struct timeval tv = { .tv_sec = (time_t)e, .tv_usec = 0 };
  settimeofday(&tv, nullptr);
  gValid = true;
  gLastSyncEp = e;
  Serial.printf("[TIME] manual set: %u\n", e);
}

}  // namespace ClockT

#endif  // ARDUINO
