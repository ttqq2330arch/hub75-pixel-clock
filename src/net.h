// ============================================================
//  net.h — WiFi 连接 + SoftAP 配网门户
//  零WiFi凭据(鸡生蛋) → SoftAP 门户解决，见 .cpp 注释
// ============================================================
#pragma once

#include <stdint.h>

namespace Net {

// 配置变动/连上时的屏显回调（在屏上跳 IP，避免串口才知道地址）
typedef void (*ShowIpFn)(const char* ip, bool isAp);

// 推送表盘成功后切表盘的回调（与 BLE 共用 main.cpp 的 onBleFace）
typedef void (*FaceSelectFn)(uint8_t idx);

// 初始化：有凭据走 STA（15s 超时）；无凭据或连接失败进配网门户。
// apName: 门户热点名，如 "PixelClock-Setup"
void begin(const char* apName, ShowIpFn showIp);
// 注册切表盘回调（setup 里在 Net::begin 之后调用一次）
void setFaceSelect(FaceSelectFn fn);
void loop();

// 清空 WiFi 凭据并重启（长按 BOOT 3s 调用）
void reset();

bool staConnected();

// 播放 FS 表盘库中的表盘（BLE 通道用）：载入并切到 REMOTE 面。
// name 不含扩展名；不存在返回 false。与 HTTP /dialplay 同一实现。
bool playDial(const char* name);

}  // namespace Net
