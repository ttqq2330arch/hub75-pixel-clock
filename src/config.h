// ============================================================
//  config.h — 硬件引脚映射与编译开关
// ------------------------------------------------------------
//  平台：ESP32-S3 N16R8（16MB Flash + 8MB PSRAM）
//  屏：P2.5 64x64 HUB75 全彩点阵（微雪规格：160x160mm，5V/4A，1/32 扫）
//
//  !! ESP32-S3 专用，不要直接套用网上 ESP32 通用映射 !!
//
//  ESP32-S3 的 GPIO26~GPIO37 被 SPI Flash / PSRAM 占用
//  （N16R8 带 8MB PSRAM 时 26~37 都被占），GPIO19/20 是 USB D-/D+，
//  GPIO0/3/45/46 是 strapping 脚。上述引脚全部不能用于 HUB75。
//
//  本映射全部落在安全区（GPIO4~18, 41~42），已回避全部约束。
// ============================================================
#pragma once

#include <stdint.h>

// ---------- HUB75 面板信号（16P 排线，面向面板丝印 IN 插）----------
// S3 安全区：不使用 19/20(USB)、26~37(Flash/PSRAM)、0/3(strapping)
//
// ✅ 2026-10-23 最终定论（依据屏背面丝印照片 panel_silk.jpg + 转接板 J1 网表）
//
// 【屏侧】丝印表格 = 标准 HUB75（连接器旁 R1G1 / B1GND / R2G2 / B2E / AB / CD /
//   CLKLAT / OEGND 八行两列），即：1=R1 2=G1 3=B1 4=GND 5=R2 6=G2 7=B2 8=E
//   9=A 10=B 11=C 12=D 13=CLK 14=LAT 15=OE 16=GND。→ GND 在 4/16，E 在 8。
//
// 【转接板侧】母座 J1 = 标准顺序但"奇偶脚两两互换"：
//   1=G1(5) 2=R1(4) 3=GND 4=B1(6) 5=G2(15) 6=R2(7) 7=E(10) 8=B2(16)
//   9=B(18) 10=A(17) 11=D(9) 12=C(8) 13=OE(12) 14=LAT(11) 15=GND 16=CLK(13)
//   → 它的 GND 在 3/15、CLK 在 16、OE 在 13，与屏正好错开一对。
//
// 【因此：排线必须"翻插"（奇偶互换），才能让 GND 落回屏的 4/16、其余 12 根信号全对】
//   翻插后仅剩 CLK/LAT/OE 三根形成环（板13/14/16 → 屏14/13/15），故在固件里对调：
//     屏 CLK(13) ← 板14 = GPIO11
//     屏 LAT(14) ← 板13 = GPIO12
//     屏 OE (15) ← 板16 = GPIO13
//   ⚠ 若哪天改成"正插"排线，请把下面 LAT/OE/CLK 恢复为 LAT=11 OE=12 CLK=13。
#define PIN_R1   4    // 上半屏 R
#define PIN_G1   5
#define PIN_B1   6
#define PIN_R2   7    // 下半屏 R
#define PIN_G2   15
#define PIN_B2   16
#define PIN_A    17   // 行选择 A~E 共 5 根（1/32 扫描必须 E！）
#define PIN_B    18
#define PIN_C    8
#define PIN_D    9
#define PIN_E    10
#define PIN_LAT  12   // Latch / STB   （翻插后 = 板13脚）
#define PIN_OE   13   // Output Enable（低有效）（翻插后 = 板16脚）
#define PIN_CLK  11   // Shift clock    （翻插后 = 板14脚）

// ---------- 板载按键 ----------
// ESP32-S3 开发板 BOOT 键在 GPIO0：短按切换表盘，长按 3s 重置 WiFi
#define PIN_BOOT_BTN 0

// ---------- 可选外设 ----------
#define PIN_SDA   41  // I2C：SHT30 温湿度（接了就自动显示）
#define PIN_SCL   42
#define PIN_BUZZER 14  // 可选无源蜂鸣器，整点报时（不焊接则悬空）

// ---------- 面板参数 ----------
#define PANEL_W   64
#define PANEL_H   64

// ---------- 功能开关 ----------
#define ENABLE_BLE          0   // v0.3.18 关闭（用户拍板「不要小程序，直接用网址」）：BLE+WiFi共存吃 ~67KB+动态开销，堆 34KB→10KB=lwIP枯竭(外部访问全死+动画乱码)。关BLE后走 v0.3.13 纯WiFi路径(setSleep false)，稳定回归；网页 http://192.168.1.52 成为唯一控制入口
#define ENABLE_SENSOR       1   // I2C SHT30 温湿度
#define ENABLE_WIFI_PORTAL  1   // SoftAP 配网门户
#define ENABLE_HOURLY_CHIME 0   // 整点蜂鸣（需焊蜂鸣器）

// ---------- 表盘索引（faces.cpp registerBuiltins 顺序）----------
#define FACE_IDX_TEST   0   // 测试图案
#define FACE_IDX_CLOCK  1   // 像素时钟（默认）
#define FACE_IDX_PLASMA 2   // 等离子动画
#define FACE_IDX_REMOTE 3   // 远程表盘（小程序 BLE 推送）

#define FW_VERSION   "0.3.23"   // 0.3.23: 网页新增"WiFi 切换"——POST /wifi?ssid=&pass= 保存新凭据并重启(含确认弹窗/当前SSID回显);连不上自动回落配网热点(STA timeout->portal 已有机制),不失联
