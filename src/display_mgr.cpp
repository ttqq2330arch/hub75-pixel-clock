// ============================================================
//  display_mgr.cpp — HUB75 面板封装实现
// ============================================================
#include "display_mgr.h"
#include "config.h"

#ifdef ARDUINO

#include <Preferences.h>

MatrixPanel_I2S_DMA* gDsp = nullptr;
uint8_t gRot = 0;   // v0.3.22：屏幕旋转 0=0° 1=90° 2=180° 3=270°（/rotate 端点改写，NVS 持久化）

namespace Display {

namespace {

// ---- 亮度管理（v0.3.11 起：颜色缩放调光，OE 全程全开）----
// 演进史（0.3.2→0.3.11 九版迭代的最终结论）：
//  - OE 窗口 PWM 调光（setBrightnessOE 把每行改成"只亮 N/64 时钟"）= 整屏深度 PWM，
//    ICN2038S 恒流源反复 establishment → 持续微闪。用户实测："加功能前正常，加完一直闪"。
//    写入时序修得再干净（后台写/flip 前写/按块去重）都没用——闪在 OE 位图内容本身。
//  - v0.3.11 正解：颜色缩放。库在每条 framebuffer 写入路径（drawPixel/fill/hline/vline）
//    把 RGB 乘 (brt/255)，OE 永远全开 → 显示行为与普通画面完全一致，无 PWM 伪影。
//    代价：低亮度暗部色阶略粗（像素时钟/动画场景可接受）。
uint8_t gTarget   = 55;    // 目标（手动）亮度
uint8_t gLastLog  = 0xFF;  // 上次打日志的亮度（去抖）
bool    gDimActive = false;
int     gDimStart  = 23 * 60;   // 23:00 默认
int     gDimEnd    = 7 * 60;    // 07:00
uint8_t gDimLevel  = 12;        // 熄灯后的最低亮度（原 20）
uint32_t gRampStartMs = 0;      // v0.3.20 软爬坡起始时刻（0 = 不在爬坡）
uint8_t  gRampFrom    = 0;      // 爬坡起始亮度
Preferences gPrefs;

int minutesOf(uint32_t epoch) {
  if (epoch == 0) return -1;
  time_t t = (time_t)epoch;
  struct tm lt;
  localtime_r(&t, &lt);
  return lt.tm_hour * 60 + lt.tm_min;
}

}  // namespace

int begin() {
  if (gDsp) return 0;

  HUB75_I2S_CFG::i2s_pins pins = {
    PIN_R1, PIN_G1, PIN_B1,
    PIN_R2, PIN_G2, PIN_B2,
    PIN_A, PIN_B, PIN_C, PIN_D, PIN_E,
    PIN_LAT, PIN_OE, PIN_CLK
  };

  // 64x64 单面板、1/32 扫描（E 脚已在 config.h 接好）
  HUB75_I2S_CFG cfg(PANEL_W, PANEL_H, 1, pins);
  cfg.double_buff = true;          // 双缓冲，无撕裂
  // v0.3.17 教训：尝试色深 8→6 位平面省 41KB 内存（治 lwIP 枯竭），结果
  // ICN2038S 驱动屏整屏黑（OE/初始化序列对位平面数敏感）——已回退 8 位。
  // 内存优化改走其它路（关 mDNS / BLE 按需），不再动显示参数。
  // 脚位已按「屏丝印 = 标准 HUB75」+「转接板 J1 = 奇偶互换」推出：排线翻插 + LAT/OE/CLK 对调
  //（详见 config.h 顶部注释）。屏背面驱动 IC 丝印实测为 CHIPONE ICN2037（Chipone 芯荐系列），
  // 列驱动同族 → 用 ICN2038S 初始化序列；若整屏偏白/亮度失控 → 改 FM6126A；若无任何初始化反应 → SHIFTREG。
  // v0.3.21 关键对齐：WuyongLab-ESP32S3-PixelClock（同一块扩展板+屏）开源固件
  // 实测能点亮，其参数为 GENERIC 驱动 + 10MHz + latch_blanking=4 + clkphase=false。
  // 我们此前 ICN2038S 特殊初始化 + 20MHz 在第二块板上点不亮 → 全部对齐到已验证参数。
  // 屏背面丝印 ICN2037（列驱动同族），但 WL 固件证明 GENERIC 无特殊初始化即可驱动。
  cfg.driver      = HUB75_I2S_CFG::SHIFTREG;  // = 0，无特殊寄存器初始化（对齐 WL 已验证配置，勿改回 ICN2038S）
  cfg.i2sspeed         = HUB75_I2S_CFG::HZ_10M;  // fork 库中 HZ_10M 实际=8MHz；WL 同级别低速，时序裕量最大
  cfg.latch_blanking   = 4;   // 对齐 WL=4：锁存前后留空，抑制重影/闪烁
  cfg.min_refresh_rate = 120;  // 对齐 WL=120（v0.3.21 改 90→120，排除刷新率差异）
  cfg.clkphase         = false;  // 与 WL 一致

  gDsp = new MatrixPanel_I2S_DMA(cfg);
  if (!gDsp->begin()) {
    Serial.printf("[DSP] panel begin() FAILED\n");
    return -1;
  }

  // ---- 开机自检（硬件已验证通过，缩短为各 1.5s，只为上电确认面板活着）----
  // ① 全屏纯白：所有 RGB 位全高 + 全行扫描 → 应整屏均匀亮白。
  // ② 左中右 红|绿|蓝 三竖带：判断 R/G/B 数据线有没有接错色。
  // v0.3.11：自检亮度也用颜色缩放（setBrightnessScale），不再写 OE 位图。
  // v0.3.20：自检亮度 110→45。v0.3.21：再降到 30（与 WL 固件开机亮度一致）。
  // 全屏纯白是供电电流峰值的最恶劣组合（64×64 全白瞬间可到 3-4A），5 引脚细线/
  // 长线供电会被拉垮 → 屏幕驱动掉电黑屏（只有 ESP32 板载灯亮）。30≈12% 电流，
  // 弱供电下绝对安全；点不亮时此自检也无诊断意义，先保证能活着。
  gDsp->setBrightness8(30);
  gDsp->fillScreen(gDsp->color565(255, 255, 255));
  gDsp->flipDMABuffer();   // 双缓冲：画完必须 flip 才上屏（否则 DMA 一直扫黑缓冲）
  Serial.printf("[DSP] SELF-TEST 1/2: FULL WHITE 1.5s (dim, 5V-safe)\n");
  delay(1500);

  gDsp->fillScreen(0);
  dspFillRect(0,  0, 21, PANEL_H, gDsp->color565(255, 0, 0));
  dspFillRect(21, 0, 21, PANEL_H, gDsp->color565(0, 255, 0));
  dspFillRect(42, 0, 22, PANEL_H, gDsp->color565(0, 0, 255));
  gDsp->flipDMABuffer();   // 同上
  Serial.printf("[DSP] SELF-TEST 2/2: R|G|B BARS 1.5s\n");
  delay(1500);

  // 严格对齐 WL：begin 后 clearScreen+flip 两次，把前后缓冲都同步成有效空屏。
  gDsp->clearScreen(); gDsp->flipDMABuffer();
  gDsp->clearScreen(); gDsp->flipDMABuffer();

  gPrefs.begin("pccfg", true);
  int8_t  b    = gPrefs.getChar("bright", -1);
  uint8_t dimS = gPrefs.getUChar("dimStart", (uint8_t)(gDimStart / 60));
  uint8_t dimE = gPrefs.getUChar("dimEnd",   (uint8_t)(gDimEnd / 60));
  gDimStart = dimS * 60;
  gDimEnd   = dimE * 60;
  gPrefs.end();

  if (b >= 0) gTarget = (uint8_t)b;
  // v0.3.21：换回官方原版 HUB75 库（WuyongLab 同款，已验证可点亮）。亮度改走官方
  // setBrightness8（OE 调光，官方实现无撕裂/微闪），不再用 fork 的 clearOEMasks/颜色缩放。
  // v0.3.20：软爬坡——不从 0 突跳到目标亮度，而是从 15 起 2.5s 内线性爬到
  // gTarget（loop() 里每 tick 推进）。开机/断电重启瞬间不再有大电流阶跃，
  // 5 引脚弱供电不再被点屏冲击拉垮。用户手动改亮度仍即时生效（setBrightness
  // 会打断爬坡——见 loop 里的判断：设置了新目标后爬坡按最新 gTarget 走）。
  gRampFrom = (gTarget > 15) ? 15 : gTarget;
  gRampStartMs = millis();
  gDsp->setBrightness8(gRampFrom);
  gLastLog = 0xFF;
  Serial.printf("[DSP] panel up: %dx%d double-buffered, brightness=%u (colour-scale)\n",
                PANEL_W, PANEL_H, gTarget);
  return 0;
}

void loop(uint32_t nowMs) {
  // v0.3.11：颜色缩放调光在库的每条绘制路径里生效，本模块无需任何每帧操作。
  // v0.3.20：开机亮度软爬坡（2.5s 线性 gRampFrom→gTarget），防点屏电流冲击。
  if (gRampStartMs && gDsp) {
    uint32_t el = nowMs - gRampStartMs;
    if (el >= 2500) {
      gDsp->setBrightness8(gDimActive ? gDimLevel : gTarget);
      gRampStartMs = 0;
    } else {
      uint32_t to = gDimActive ? gDimLevel : gTarget;
      uint32_t v  = gRampFrom + (to - gRampFrom) * el / 2500;
      gDsp->setBrightness8((uint8_t)v);
    }
  }
}

// 息屏时段判断（外部每 tick 传 nowEpoch 进来）。
// 只更新 gDimActive 状态；昼夜切换时立刻应用一次缩放系数（setBrightnessScale 是
// 纯粹的系数赋值，不碰 framebuffer，无任何竞态），下一帧渲染自动按新系数出图。
void tickDim(uint32_t nowEpoch) {
  int m = minutesOf(nowEpoch);
  if (m < 0) {
    gDimActive = false;
  } else {
    bool next = (gDimStart > gDimEnd) ? (m >= gDimStart || m < gDimEnd)
                                      : (m >= gDimStart && m < gDimEnd);
    if (next != gDimActive) {
      gDimActive = next;
      if (gDsp) gDsp->setBrightness8(gDimActive ? gDimLevel : gTarget);
      Serial.printf("[DSP] dim %s -> scale %u\n", gDimActive ? "ON" : "OFF",
                    gDimActive ? gDimLevel : gTarget);
    }
  }
}

void setBrightness(uint8_t v) {
  gTarget = v;
  gPrefs.begin("pccfg", false);
  gPrefs.putChar("bright", (int8_t)v);
  gPrefs.end();
  gRampStartMs = 0;   // 用户手动调亮度 = 立即打断开机软爬坡
  // v0.3.11：颜色缩放调光——只改库里的缩放系数（不碰 framebuffer/OE），
  // 下一帧渲染自动按新系数出图。零竞态、零 PWM、零闪。
  if (gDsp && !gDimActive) gDsp->setBrightness8(v);
  if (v != gLastLog) {
    Serial.printf("[DSP] brightness -> %u (dim=%d)\n", v, gDimActive ? 1 : 0);
    gLastLog = v;
  }
}

uint8_t brightness() { return gTarget; }

void setDimSchedule(int startMin, int endMin, uint8_t dimLevel) {
  gDimStart = startMin; gDimEnd = endMin; gDimLevel = dimLevel;
}

bool currentlyDim() { return gDimActive; }

}  // namespace Display

#endif  // ARDUINO
