// ============================================================
//  sensor.cpp — SHT30 实现
// ============================================================
#include "sensor.h"
#include "config.h"

#ifdef ARDUINO

#include <Arduino.h>
#include <Wire.h>

namespace Sensor {

namespace {
bool     gPresent   = false;
bool     gBegan     = false;
float    gT = 0, gH = 0;
uint32_t gLastRead  = 0;
const uint32_t READ_INTERVAL = 2000;
}

void begin() {
  if (gBegan) return;
  gBegan = true;
#if ENABLE_SENSOR
  Wire.begin((int)PIN_SDA, (int)PIN_SCL, 400000);
  // 发送一次单次测量，读成功才算在线
  Wire.beginTransmission(0x44);
  Wire.write(0x24); Wire.write(0x00);
  if (Wire.endTransmission() != 0) {
    Serial.println("[SENSOR] SHT30 not found (0x44)");
    return;
  }
  gPresent = true;
  Serial.println("[SENSOR] SHT30 online (0x44)");
#endif
}

bool present() { return gPresent; }

bool read(float& tempC, float& humi) {
#if !ENABLE_SENSOR
  return false;
#else
  if (!gPresent) return false;
  uint32_t now = millis();
  if (now - gLastRead >= READ_INTERVAL) {
    gLastRead = now;
    Wire.beginTransmission(0x44);
    Wire.write(0x24); Wire.write(0x00);
    if (Wire.endTransmission() != 0) return false;
    delay(16);   // 高重复性转换时间
    if (Wire.requestFrom((uint8_t)0x44, (uint8_t)6) != 6) return false;
    uint8_t d[6];
    for (int i = 0; i < 6; ++i) d[i] = Wire.read();
    uint16_t rt = ((uint16_t)d[0] << 8) | d[1];
    uint16_t rh = ((uint16_t)d[3] << 8) | d[4];
    gT = -45.0f + 175.0f * ((float)rt / 65535.0f);
    gH = 100.0f * ((float)rh / 65535.0f);
  }
  tempC = gT;
  humi  = gH;
  return true;
#endif
}

}  // namespace Sensor

#endif  // ARDUINO
