// ============================================================
//  sensor.h/cpp — SHT30 温湿度传感器（I2C，地址 0x44）
//  没接传感器时 read() 返回 false，界面显示 "--"。
//  自写 I2C 单次测量，零第三方依赖：
//    命令 0x24,0x00 (single-shot, high repeatability, no clock stretch)
//    等待 15ms 后读 6 字节: T_msb T_lsb T_crc H_msb H_lsb H_crc
// ============================================================
#pragma once

#include <stdint.h>

namespace Sensor {

void begin();                         // 懒初始化，检测不到芯片自动禁用
bool read(float& tempC, float& humi); // 内部 2s 节流
bool present();

}  // namespace Sensor
