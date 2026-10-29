// ============================================================
//  face_clock.cpp — 像素时钟（主表盘）
//
//  布局（64x64）：
//    y  2  日期   MM-DD WWW      小字（白 60%）
//    y 10  温湿度 23.5\x01 56%    小字（辅色）  没接传感器显示 --
//    y 17  分隔虚线（暗）
//    y 19  HH:MM               大字 scale 2（主色），冒号 500ms 闪烁
//    y 36  秒进度条 64 格（已过暗主色/当前格点缀色闪烁/未过暗灰）
//    y 42  状态行 左 OK/SYNC  右 秒两位数（scale 1）
// ============================================================
#include "face.h"
#include "display_mgr.h"
#include "font5x7.h"
#include "sensor.h"
#include "clock_time.h"
#include "config.h"

#include <time.h>
#include <math.h>
#include <Preferences.h>

#ifndef NATIVE
#define NATIVE 0
#endif

namespace {

inline uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

// ---- 配色方案 ----
struct Palette { const char* name; uint16_t fg; uint16_t dim; uint16_t accent; };
static const Palette PALETTES[] = {
  { "AMBER",  rgb(255,176,  0), rgb( 64, 44,  0), rgb(255,255,255) },  // 琥珀
  { "CYAN",   rgb(  0,229,255), rgb(  0, 57, 64), rgb(255,255,255) },  // 青
  { "GREEN",  rgb( 57,255,106), rgb( 14, 64, 26), rgb(  0,229,255) },  // 绿
  { "PURPLE", rgb(179,107,255), rgb( 45, 27, 64), rgb(255,235,170) },  // 紫
};
const int PALETTE_COUNT = 4;

Palette gPal = PALETTES[0];
int     gPalIdx = 0;

static const char* WD[] = { "SUN","MON","TUE","WED","THU","FRI","SAT" };

void loadPalette() {
  Preferences p;
  p.begin("pccfg", true);
  gPalIdx = p.getUChar("pal", 0);
  if (gPalIdx >= PALETTE_COUNT) gPalIdx = 0;
  p.end();
  gPal = PALETTES[gPalIdx];
}

// 暗化后的前景色（秒条"已过"段）
uint16_t dimColor(uint16_t c, float k) {
  uint8_t r = (uint8_t)(((c >> 11) & 0x1F) * 255 / 31 * k);
  uint8_t g = (uint8_t)(((c >> 5)  & 0x3F) * 255 / 63 * k);
  uint8_t b = (uint8_t)((c & 0x1F) * 255 / 31 * k);
  return rgb(r, g, b);
}

char gDate[12]   = "-- --";
char gLine2[16]  = "--";

class FaceClock : public WatchFace {
public:
  FaceClock() : WatchFace("clock", "PIXEL CLOCK") {
    loadPalette();
  }

  void onSelect() override {
    loadPalette();
  }

  void tick(const FaceEnv& env) override {
    gDsp->fillScreen(0x0000);

    // ---------- 顶部：日期 ----------
    if (env.epochValid && env.nowEpoch > 1700000000) {
      time_t t = (time_t)env.nowEpoch;
      struct tm lt;
      localtime_r(&t, &lt);
      snprintf(gDate, sizeof(gDate), "%02d-%02d %s",
               lt.tm_mon + 1, lt.tm_mday, WD[lt.tm_wday]);
    }
    Pix::drawText(gDsp, (PANEL_W - Pix::textWidth(gDate)) / 2, 1,
                  gDate, rgb(200, 200, 200));

    // ---------- 第二行：温湿度 ----------
    float t = 0, h = 0;
    if (Sensor::read(t, h)) {
      snprintf(gLine2, sizeof(gLine2), "%d\x01 %d%%",
               (int)(t < 0 ? t - 0.5 : t + 0.5), (int)(h + 0.5));
    } else {
      snprintf(gLine2, sizeof(gLine2), "--" " --");
    }
    Pix::drawText(gDsp, (PANEL_W - Pix::textWidth(gLine2)) / 2, 9,
                  gLine2, rgb(170, 170, 170));

    // ---------- 分隔虚线 ----------
    for (int x = 0; x < PANEL_W; x += 2)
      dspDrawPixel(x, 17, dimColor(gPal.fg, 0.25));

    // ---------- 中部大字 HH:MM ----------
    char hm[6] = "--:--";
    int  sec = -1;
    if (env.epochValid && env.nowEpoch > 1700000000) {
      time_t tt = (time_t)env.nowEpoch;
      struct tm lt;
      localtime_r(&tt, &lt);
      snprintf(hm, sizeof(hm), "%02d:%02d", lt.tm_hour, lt.tm_min);
      sec = lt.tm_sec;
    }
    bool colonOn = !env.epochValid ? true : ((env.nowMs / 500) % 2 == 0);
    // 逐字放大绘制 HH:MM（scale 2，总宽 58，x=3 居中；冒号按 colonOn 闪烁）
    drawBigHm(hm, colonOn, env.epochValid);

    // ---------- 秒进度条（y=36..38, 三行粗条）----------
    // 64 格对应 60 秒（前 4 格留白）；已过=暗主色，当前秒=点缀色闪烁，未过=暗灰
    for (int i = 0; i < 60; ++i) {
      int cx = i + 2;
      uint16_t c;
      if (!env.epochValid)           c = dimColor(rgb(60, 60, 60), 1.0);
      else if (sec < 0)              c = dimColor(rgb(60, 60, 60), 1.0);
      else if (i < sec)              c = dimColor(gPal.fg, 0.35);
      // 当前秒：原来 250ms 闪一次点缀色（4Hz 频闪很扎眼），改为常亮
      else if (i == sec)             c = gPal.accent;
      else                           c = rgb(24, 24, 24);
      for (int dy = 0; dy < 3; ++dy) dspDrawPixel(cx, 36 + dy, c);
    }

    // ---------- 状态行 ----------
    const char* status = env.epochValid ? "OK" : "SYNC";
    Pix::drawText(gDsp, 2, 41, status, env.epochValid ? gPal.dim : gPal.accent);
    if (env.epochValid && sec >= 0) {
      char buf[3];
      snprintf(buf, sizeof(buf), "%02d", sec);
      Pix::drawText(gDsp, PANEL_W - 2 - Pix::textWidth(buf), 41, buf, gPal.dim);
    }

    // ---------- 底部呼吸点（标识固件活着）----------
    {
      float ph = (float)(env.nowMs % 2000) / 2000.0f;
      float b  = 0.5f - 0.5f * cosf(ph * 6.2831853f);
      uint16_t c = (uint8_t)(b * 255) > 128 ? dimColor(gPal.fg, 0.6)
                                           : dimColor(gPal.fg, 0.15);
      for (int dy = 0; dy < 3; ++dy)
        for (int dx = 0; dx < 3; ++dx)
          dspDrawPixel(PANEL_W / 2 - 1 + dx, PANEL_H - 3 + dy, c);
    }
  }

  void render() override {}

private:
  // 逐字放大绘制 HH:MM（冒号按 colonOn 决定是否绘制）
  void drawBigHm(const char* s, bool colonOn, bool valid) {
    uint16_t fg = gPal.fg;
    int x = 3;
    for (const char* p = s; *p; ++p) {
      if (*p == ':') {
        if (colonOn) {
          for (int col = 0; col < 5; ++col) {
            uint8_t bits = Pix::glyph(':', col);
            for (int row = 0; row < 7; ++row) {
              if (bits & (1 << row)) {
                for (int sy = 0; sy < 2; ++sy)
                  for (int sx = 0; sx < 2; ++sx)
                    dspDrawPixel(x + col * 2 + sx, 19 + row * 2 + sy, fg);
              }
            }
          }
        }
        x += 12;
        continue;
      }
      for (int col = 0; col < 5; ++col) {
        uint8_t bits = Pix::glyph(*p, col);
        for (int row = 0; row < 7; ++row) {
          if (bits & (1 << row)) {
            for (int sy = 0; sy < 2; ++sy)
              for (int sx = 0; sx < 2; ++sx)
                dspDrawPixel(x + col * 2 + sx, 19 + row * 2 + sy, fg);
          }
        }
      }
      x += 12;
    }
    (void)valid;
  }
};

}  // namespace

WatchFace* createFaceClock() { static FaceClock f; return &f; }
