// ============================================================
//  display_mgr.h — HUB75 面板封装
//  创建 MatrixPanel_I2S_DMA、亮度管理、夜间自动息屏。
// ============================================================
#pragma once

#include <stdint.h>

#ifdef ARDUINO
#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>
#endif

namespace Display {

// 初始化 DMA 面板（内部按 config.h 引脚建对象）。
// 返回 0 成功；负值失败码用于串口诊断。
int begin();

// 每帧：自动息屏时段/亮度调度
void loop(uint32_t nowMs);

// 按当前 epoch 判断是否在夜间息屏时段，更新内部状态
void tickDim(uint32_t nowEpoch);

// 目标亮度 0~255（内部做 CIE 感知过渡，避免突变刺眼）
void setBrightness(uint8_t v);
uint8_t brightness();

// 夜间息屏：startMin/endMin（0~1439 分钟，结束小于开始表示跨夜）
void setDimSchedule(int startMin, int endMin, uint8_t dimLevel);
bool currentlyDim();

}  // namespace Display

#ifdef ARDUINO
extern MatrixPanel_I2S_DMA* gDsp;   // 全局显示对象（nullptr = 未初始化）

// ---- v0.3.22：屏幕旋转（0=0° 1=90°CW 2=180° 3=270°CW）----
// 64×64 方屏，全画面绕中心旋转。所有绘制统一走 dspDrawPixel/dspFillRect，
// 时钟/表盘/动画/叠加文字整体旋转，视角与安装方向无关。
extern uint8_t gRot;

inline void dspDrawPixel(int x, int y, uint16_t c) {
  if (!gDsp) return;
  int ox = x, oy = y;
  switch (gRot) {
    case 1:  ox = 63 - y; oy = x; break;
    case 2:  ox = 63 - x; oy = 63 - y; break;
    case 3:  ox = y;      oy = 63 - x; break;
    default: break;
  }
  gDsp->drawPixel(ox, oy, c);
}

inline void dspFillRect(int x, int y, int w, int h, uint16_t c) {
  if (!gDsp) return;
  int ox = x, oy = y, ow = w, oh = h;
  switch (gRot) {
    case 1:  ox = 64 - h - y; oy = x;      ow = h; oh = w; break;
    case 2:  ox = 64 - w - x; oy = 64 - h - y; break;
    case 3:  ox = y;          oy = 64 - w - x; ow = h; oh = w; break;
    default: break;
  }
  gDsp->fillRect(ox, oy, ow, oh, c);
}
#endif
