// ============================================================
//  face_test.cpp — 接线验证表盘
//  用途：烧录后第一眼确认接线是否正确。判读方法（README 详述）：
//    * 颜色互换   → R/G/B 三根线插反
//    * 上下分裂   → R1/R2（上半/下半屏）插反
//    * 行条纹错乱 → A~E 顺序错（64x64 是 1/32 扫描，5 根都要对）
//    * 花屏/全乱  → CLK/LAT/OE 错，或 VCC 电流不足
// ============================================================
#include "face.h"
#include "display_mgr.h"
#include "font5x7.h"

#ifndef NATIVE
#define NATIVE 0
#endif

namespace {

// RGB565 工具
inline uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

enum Phase { P_BARS, P_RGB_SOLID, P_ROW_SCAN, P_CORNERS, DONE };
Phase  gPhase = P_BARS;
uint32_t gPhaseStart = 0;
int    gSub = 0;         // P_RGB_SOLID 子步骤
bool   gInited = false;

void drawBars() {
  gDsp->fillScreen(0);
  // 顶部三原色横条（高亮区：1/4 高）
  for (int x = 0; x < PANEL_W; ++x) {
    for (int y = 0; y < 16; ++y) {
      uint16_t c;
      if      (y < 5)  c = rgb(255, 0, 0);     // 红
      else if (y < 10) c = rgb(0, 255, 0);     // 绿
      else if (y < 15) c = rgb(0, 0, 255);     // 蓝
      else             c = rgb(255, 255, 255);  // 白
      dspDrawPixel(x, y, c);
    }
  }
  // 下部彩虹竖条
  static const uint16_t rainbow[] = {
    rgb(255,0,0), rgb(255,127,0), rgb(255,255,0), rgb(0,255,0),
    rgb(0,255,255), rgb(0,0,255), rgb(255,0,255)
  };
  for (int x = 0; x < PANEL_W; ++x) {
    uint16_t c = rainbow[(x * 7) / PANEL_W];
    for (int y = 18; y < PANEL_H; ++y) dspDrawPixel(x, y, c);
  }
  Pix::drawText(gDsp, 2, 56, "BARS", rgb(255,255,255));
}

void drawRgbSolid(uint16_t c, const char* label) {
  gDsp->fillScreen(c);
  // 中央反色小字，方便确认像素方向
  Pix::drawText(gDsp, 8, 28, label, 0x0000, 2);
}

void drawRowScan() {
  static uint16_t col = 0;
  gDsp->fillScreen(0);
  // 上半屏亮奇数行 / 下半屏亮偶数行 —— 一眼看出上下半屏接线
  for (int x = 0; x < PANEL_W; ++x) {
    for (int y = 0; y < 32; ++y)
      if (y % 2 == 0) dspDrawPixel(x, y, col ? 0x07E0 : 0xF800);
    for (int y = 32; y < PANEL_H; ++y)
      if (y % 2 == 1) dspDrawPixel(x, y, col ? 0xF800 : 0x07E0);
    col ^= 1;
  }
  Pix::drawText(gDsp, 6, 28, "UPDN", rgb(255,255,255), 3);
}

void drawCorners() {
  gDsp->fillScreen(0);
  // 四角 2x2 定位块 + 中心十字
  for (int i = 0; i < 2; ++i) for (int j = 0; j < 2; ++j) {
    dspDrawPixel(i, j, 0xF800);
    dspDrawPixel(PANEL_W - 1 - i, j, 0x07E0);
    dspDrawPixel(i, PANEL_H - 1 - j, 0x001F);
    dspDrawPixel(PANEL_W - 1 - i, PANEL_H - 1 - j, 0xFFE0);
  }
  for (int i = -6; i <= 6; ++i) {
    dspDrawPixel(PANEL_W / 2 + i, PANEL_H / 2, 0xFFFF);
    dspDrawPixel(PANEL_W / 2, PANEL_H / 2 + i, 0xFFFF);
  }
  Pix::drawText(gDsp, 4, 4,  "1", rgb(255,255,255));
  Pix::drawText(gDsp, 56, 4, "2", rgb(255,255,255));
  Pix::drawText(gDsp, 4, 56, "3", rgb(255,255,255));
  Pix::drawText(gDsp, 56, 56, "4", rgb(255,255,255));
}

class FaceTest : public WatchFace {
public:
  FaceTest() : WatchFace("test", "TEST PATTERN") {}

  void onSelect() override {
    gPhase = P_BARS; gSub = 0; gPhaseStart = millis();
    gInited = true;
  }

  void tick(const FaceEnv& env) override {
    uint32_t elapsed = env.nowMs - gPhaseStart;
    switch (gPhase) {
      case P_BARS:
        drawBars();
        if (elapsed > 2500) next(P_RGB_SOLID, env.nowMs);
        break;
      case P_RGB_SOLID: {
        // 顺序：白→红→绿→蓝→黑（黑屏用来观察行扫描的余晖）
        static const uint16_t cols[] = {0xFFFF, 0xF800, 0x07E0, 0x001F, 0x0000};
        drawRgbSolid(cols[gSub], gSub == 0 ? "WHT" : gSub == 1 ? "RED" :
                                   gSub == 2 ? "GRN" : gSub == 3 ? "BLU" : "BLK");
        if (elapsed > 1200) { gSub = (gSub + 1) % 5; gPhaseStart = env.nowMs; }
        break;
      }
      case P_ROW_SCAN:
        drawRowScan();
        if (elapsed > 3000) next(P_CORNERS, env.nowMs);
        break;
      case P_CORNERS:
        drawCorners();
        if (elapsed > 3000) next(P_BARS, env.nowMs);
        break;
      default: break;
    }
  }

  void render() override {
    if (!gInited) { onSelect(); return; }
    // tick 里已直接绘制；主循环统一 flipBuffer，这里空着
  }

private:
  void next(Phase p, uint32_t now) { gPhase = p; gPhaseStart = now; }
};

}  // namespace

WatchFace* createFaceTest() { static FaceTest f; return &f; }
