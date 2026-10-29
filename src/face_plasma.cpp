// ============================================================
//  face_plasma.cpp — 等离子动画（彩色能力演示 + 氛围灯）
//  经典 sine plasma，HUB75 上跑 64x64 每帧 4096 像素纯计算，
//  S3@240MHz 稳定 25+ FPS。可用作夜间氛围/挂机动画。
// ============================================================
#include "face.h"
#include "display_mgr.h"
#include "config.h"

#include <math.h>

namespace {

inline uint16_t rgb565(uint8_t r, uint8_t g, uint8_t b) {
  return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
}

uint32_t gSeed = 0;

class FacePlasma : public WatchFace {
public:
  FacePlasma() : WatchFace("plasma", "PLASMA") {}

  void tick(const FaceEnv& env) override {
    gSeed = env.nowMs / 40;   // 25fps 相位
    float t = (float)gSeed * 0.06f;
    for (int y = 0; y < PANEL_H; ++y) {
      for (int x = 0; x < PANEL_W; ++x) {
        float v = sinf(x * 0.10f + t)
                + sinf(y * 0.14f + t * 1.3f)
                + sinf((x + y) * 0.09f + t * 0.7f)
                + sinf(sqrtf((float)((x - 32) * (x - 32) + (y - 32) * (y - 32)))
                       * 0.11f - t * 1.1f);
        // v ∈ [-4, 4] → 色相
        float h = (v + 4.0f) / 8.0f;   // 0..1
        // HSV → RGB (固定 S=1, V=1)
        float r, g, b;
        hueRgb(h, r, g, b);
        dspDrawPixel(x, y, rgb565((uint8_t)(r * 255), (uint8_t)(g * 255),
                                     (uint8_t)(b * 255)));
      }
    }
  }

  void render() override {}

private:
  static void hueRgb(float h, float& r, float& g, float& b) {
    int i = (int)(h * 6.0f);
    float f = h * 6.0f - (float)i;
    switch (i % 6) {
      case 0: r = 1;     g = f;     b = 0;     break;
      case 1: r = 1 - f; g = 1;     b = 0;     break;
      case 2: r = 0;     g = 1;     b = f;     break;
      case 3: r = 0;     g = 1 - f; b = 1;     break;
      case 4: r = f;     g = 0;     b = 1;     break;
      default:r = 1;     g = 0;     b = 1 - f; break;
    }
  }
};

}  // namespace

WatchFace* createFacePlasma() { static FacePlasma f; return &f; }
