// ============================================================
//  faces_access.h — 当前表盘索引的跨模块访问
//  BLE 特征 / 物理按键都通过它请求切换，main 循环统一执行。
// ============================================================
#pragma once

namespace FacesAcc {

extern int gCurrent;    // 当前生效表盘索引
extern int gDesired;    // 请求切换的索引（<0 = 无请求）

// 请求切换到 idx（自动循环取模；idx<0 视为无请求）
void request(int idx);
int  current();

}  // namespace FacesAcc
