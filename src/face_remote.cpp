// ============================================================
//  face_remote.cpp — BLE 下发的远程表盘
//  帧协议见 docs/face-push-protocol.md：
//    0x01 数据块 [01][off_lo][off_hi][len][payload...]
//    0x02 提交   [02][crc_lo][crc_hi]   CRC16-XMODEM 全帧校验
//    0x03 中止   [03]
// ============================================================
#include "face_remote.h"
#include "display_mgr.h"
#include "font5x7.h"

#include <string.h>
#include <stdlib.h>
#include <esp_heap_caps.h>
#include <LittleFS.h>

#ifdef ARDUINO

namespace RemoteFace {

uint8_t  gBuf[FRAME_BYTES];
bool     gValid      = false;
uint8_t  gStatus     = ST_IDLE;
uint32_t gLastChunkMs = 0;

// ---- 动画背景模式 ----
uint8_t*  gAnimBuf     = nullptr;   // PSRAM/堆上分配
uint8_t   gAnimCap     = 0;         // 实际可用帧数上限
uint8_t   gAnimFrames  = 0;         // >=2 动画模式；0/1 = 单帧
uint8_t   gAnimFps     = 10;
bool      gAnimOverlay = false;
uint8_t   gAnimIdx     = 0;
uint32_t  gAnimLastMs  = 0;
bool      gAnimBurst   = false;   // 整分钟触发模式（帧布局见 beginAnim 注释）

// 叠加时钟的缓存时间（tick 里从 env 拿，render 无 env）
static uint32_t sOvEpoch = 0;
static bool     sOvValid = false;

// ---- 叠加时钟可调参数（定义）----
uint8_t gOvMode  = 0;    // 0=经典 HH:MM  1=方块数字（7x7 马里奥字体）
int8_t  gOvX     = -1;   // mode0: -1=居中；mode1: 小时块 x
int8_t  gOvY     = 46;   // mode0: 文本 y；mode1: 块 y
int8_t  gOvX2    = 34;   // mode1: 分钟块 x
uint8_t gOvScale = 2;    // mode0 字号 1..2
uint8_t gOvFG    = 0;    // mode0 前景色 0=白 1=黑 2=黄

void overlayResetDefaults(uint8_t mode) {
  gOvMode = mode ? 1 : 0;
  if (gOvMode == 0) { gOvX = -1; gOvY = 46; gOvScale = 2; gOvFG = 0; }
  else              { gOvX = 12; gOvY = 11; gOvX2 = 34; }
}

// mode0 前景色 → RGB565
static uint16_t ovFGColor() {
  switch (gOvFG) {
    case 1:  return 0x0000;   // 黑
    case 2:  return 0xFFE0;   // 黄
    default: return 0xFFFF;   // 白
  }
}

bool initAnimBuf() {
  if (gAnimBuf) return true;
  // 优先 PSRAM（8MB，只读不写 DMA，带宽无压力）
  gAnimBuf = (uint8_t*)heap_caps_malloc((size_t)MAX_ANIM_FRAMES * FRAME_BYTES,
                                        MALLOC_CAP_SPIRAM);
  if (gAnimBuf) {
    gAnimCap = MAX_ANIM_FRAMES;
    Serial.printf("[ANIM] buf on PSRAM: %u frames (%u KB)\n",
                  gAnimCap, (unsigned)((size_t)gAnimCap * FRAME_BYTES / 1024));
    return true;
  }
  // 退回普通堆
  gAnimBuf = (uint8_t*)malloc((size_t)MAX_ANIM_FRAMES_SRAM * FRAME_BYTES);
  if (gAnimBuf) {
    gAnimCap = MAX_ANIM_FRAMES_SRAM;
    Serial.printf("[ANIM] buf on heap: %u frames\n", gAnimCap);
    return true;
  }
  Serial.println("[ANIM] buf alloc FAILED");
  return false;
}

bool beginAnim(uint8_t frames, uint8_t fps, bool overlay, bool burst) {
  if (!gAnimBuf && !initAnimBuf()) return false;
  if (frames < 1) frames = 1;
  if (frames > gAnimCap) frames = gAnimCap;
  if (fps < 1) fps = 1;
  if (fps > 30) fps = 30;
  if (burst && frames < 3) burst = false;   // 爆发模式至少 3 帧（2 序列 + 1 待机）
  gAnimFrames  = frames;
  gAnimFps     = fps;
  gAnimOverlay = overlay;
  gAnimBurst   = burst;
  gAnimIdx     = 0;
  gAnimLastMs  = millis();
  gValid       = true;
  gStatus      = ST_OK;
  Serial.printf("[ANIM] start frames=%u fps=%u overlay=%u burst=%u\n",
                frames, fps, overlay ? 1 : 0, burst ? 1 : 0);
  return true;
}

void animTick(uint32_t nowMs) {
  if (gAnimFrames < 2) return;
  uint32_t interval = 1000UL / gAnimFps;
  if (nowMs - gAnimLastMs < interval) return;
  gAnimLastMs = nowMs;
  gAnimIdx = (uint8_t)((gAnimIdx + 1) % gAnimFrames);
}

const uint8_t* animFrame(uint8_t idx) {
  if (!gAnimBuf || idx >= gAnimCap) return gBuf;
  return gAnimBuf + (size_t)idx * FRAME_BYTES;
}

// 接收超时：3 秒没有新数据块就放弃当前传输
static const uint32_t RX_TIMEOUT_MS = 3000;

void beginRx() {
  gStatus = ST_RECEIVING;
  gLastChunkMs = millis();
}

bool writeChunk(uint16_t off, const uint8_t* data, uint16_t len) {
  if (!data || len == 0) return false;
  // 动画缓冲已分配时允许写到整个动画区（HTTP 推多帧用）
  uint32_t bound = gAnimBuf ? (uint32_t)gAnimCap * FRAME_BYTES : FRAME_BYTES;
  if ((uint32_t)off + len > bound) return false;          // 越界拒绝
  if (gStatus != ST_RECEIVING && gStatus != ST_IDLE) return false;
  if (off < FRAME_BYTES) {
    memcpy(gBuf + off, data, len);                         // 帧0：单帧路径（BLE 兼容）
    if (gAnimBuf) memcpy(gAnimBuf + off, data, len);       // 同步进动画区
  } else {
    memcpy(gAnimBuf + off, data, len);                     // 帧1..N：只进动画区
  }
  gStatus = ST_RECEIVING;
  gLastChunkMs = millis();
  return true;
}

bool commit(uint16_t crc) {
  if (crc16(gBuf, FRAME_BYTES) != crc) {
    gStatus = ST_CRC_FAIL;
    return false;
  }
  gValid  = true;
  gStatus = ST_OK;
  gAnimFrames = 0;        // BLE 单帧推送 → 退出动画模式（M3 协议兼容）
  gAnimOverlay = false;
  // [DBG] 客观验证：缓冲里到底有没有非黑像素
  uint32_t nz = 0;
  for (uint32_t i = 0; i < FRAME_BYTES; i += 2) {
    uint16_t px = (uint16_t)gBuf[i] | ((uint16_t)gBuf[i + 1] << 8);
    if (px) ++nz;
  }
  Serial.printf("[DBG] commit OK  px0=%02X%02X  nonzero_px=%u/%u\n",
                gBuf[0], gBuf[1], nz, (uint32_t)(FRAME_BYTES / 2));
  return true;
}

void abortRx() {
  gStatus = ST_ABORT;
}

bool tickTimeout(uint32_t nowMs) {
  if (gStatus != ST_RECEIVING) return false;
  if (nowMs - gLastChunkMs < RX_TIMEOUT_MS) return false;
  gStatus = ST_ABORT;
  return true;
}

uint16_t crc16(const uint8_t* data, uint32_t len) {
  uint16_t crc = 0x0000;                       // XMODEM：init 0
  for (uint32_t i = 0; i < len; ++i) {
    crc ^= (uint16_t)data[i] << 8;
    for (int b = 0; b < 8; ++b) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

// ---------------- 表盘对象 ----------------

FaceRemoteImpl::FaceRemoteImpl() : WatchFace("remote", "REMOTE (APP)") {}

void FaceRemoteImpl::onSelect() {
  // 每次选中刷新一次占位/内容（render 每帧都重画，这里无需做事）
}

void FaceRemoteImpl::tick(const FaceEnv& env) {
  // 缓存时间供 render 叠加时钟（render 无 env）
  sOvEpoch = env.nowEpoch;
  sOvValid = env.epochValid;
  animTick(env.nowMs);          // 动画帧推进
}

// ---------- 叠加实时时钟 ----------
// mode 0：HH:MM（scale 可调，黑色描边保底可读）+ 底部秒进度条
// mode 1：方块数字（ult-mario/ult-luigi 风格）——先把两位数字带填成块体色
//         （盖掉 PNG 里烘焙的旧数字），再用 7x7 马里奥字体画实时 HH/MM。
//         字形/排版移植自 vandalon/ultimatrix 的 Clockface.cpp（PolyForm Noncommercial，
//         个人使用），块参数 kBlockX={12,34} kBlockTop=11 kBlockSize=19 与其 PNG 一致。

// 7x7「超级马里奥」字体（ultimatrix MiniFont 的大号版，'#'=墨点）
static const char* const kGlyph7[10][7] = {
  {".#####.", "##..###", "##..###", "##..###", "##..###", "##..###", ".#####."},  // 0
  {"..###..", ".####..", "..###..", "..###..", "..###..", "..###..", ".#####."},  // 1
  {".#####.", "##..###", "....###", "..####.", ".###...", "###....", "#######"},  // 2
  {".######", "....##.", "..###..", "....##.", "....###", "##..###", ".#####."},  // 3
  {"...###.", "..####.", ".##.##.", "##..##.", "#######", "....##.", "....##."},  // 4
  {"######.", "##.....", "######.", "....###", "....###", "##..###", ".#####."},  // 5
  {".#####.", "##.....", "######.", "##..###", "##..###", "##..###", ".#####."},  // 6
  {"#######", "##..###", "....##.", "...##..", "..##...", "..##...", "..##..."},  // 7
  {".#####.", "##..###", "##..###", ".#####.", "##..###", "##..###", ".#####."},  // 8
  {".#####.", "##..###", "##..###", ".######", "....###", "....###", ".#####."},  // 9
};

// 数字左右实际有墨的列（"1" 比 "0" 窄，用于居中）
static void inkBounds7(int digit, int& first, int& last) {
  first = 7; last = 0;
  for (int row = 0; row < 7; row++)
    for (int col = 0; col < 7; col++)
      if (kGlyph7[digit % 10][row][col] == '#') {
        if (col < first) first = col;
        if (col > last)  last  = col;
      }
}

static void drawDigit7(int x, int y, int digit, uint16_t color) {
  for (int row = 0; row < 7; row++)
    for (int col = 0; col < 7; col++)
      if (kGlyph7[digit % 10][row][col] == '#') dspDrawPixel(x + col, y + row, color);
}

// 从当前帧采样块体色（避开铆钉 x+2..3/y+2..3 与数字带 y+6..12）
static uint16_t sampleBlockBody(const uint8_t* frame, int bx, int by) {
  const uint8_t* p = frame + ((size_t)(by + 4) * PANEL_W + (bx + 4)) * 2;
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

// 方块模式：Hour 块 (bx,by) / Minute 块 (bx2,by)，块 19x19，数字带 y+6..y+12
static void drawBlockDigits(int bx, int by, int bx2, int hh, int mm) {
  const uint16_t black = 0x0000;
  const uint8_t* frame = (gAnimFrames >= 2) ? animFrame(gAnimIdx) : gBuf;
  const int n = 19;                       // kBlockSize
  int blocks[2] = {bx, bx2};
  int vals[2]   = {hh, mm};
  for (int b = 0; b < 2; b++) {
    int x = blocks[b], y = by;
    if (x < 0 || y < 0 || x + n > PANEL_W || y + n > PANEL_H) continue;  // 越界不画
    // 1) 数字带填块体色：盖掉 PNG 烘焙数字，也清掉上分钟的残留
    uint16_t body = sampleBlockBody(frame, x, y);
    dspFillRect(x + 1, y + 6, 17, 7, body);
    // 2) 排版：两位数字墨点居中，间距 8（奇数补偿 9），移植自 ultimatrix drawBlock
    int t = vals[b] / 10, u = vals[b] % 10;
    int fA, lA, fB, lB;
    inkBounds7(t, fA, lA); inkBounds7(u, fB, lB);
    int pitch = 8;
    if ((n - (pitch + lB - fA + 1)) % 2) pitch = 9;
    int start = (n - (pitch + lB - fA + 1)) / 2 - fA;
    drawDigit7(x + start,      y + 6, t, black);
    drawDigit7(x + start + pitch, y + 6, u, black);
  }
}

static void drawOverlayClock() {
  char buf[6];
  int  sec = 0;
  if (sOvValid) {
    uint32_t t = sOvEpoch + 8UL * 3600UL;          // UTC+8（北京时间）
    uint32_t hh = (t / 3600) % 24;
    uint32_t mm = (t / 60) % 60;
    sec = (int)(t % 60);
    snprintf(buf, sizeof(buf), "%02u:%02u", (unsigned)hh, (unsigned)mm);
  } else {
    snprintf(buf, sizeof(buf), "--:--");
  }
  if (gOvMode == 1) {
    // 方块数字模式：未同步时间时保留 PNG 烘焙数字（不擦不画）
    if (!sOvValid) return;
    uint32_t t  = sOvEpoch + 8UL * 3600UL;
    drawBlockDigits(gOvX, gOvY, gOvX2, (int)((t / 3600) % 24), (int)((t / 60) % 60));
    return;
  }
  const int scale = (gOvScale >= 1 && gOvScale <= 2) ? gOvScale : 2;
  int w = Pix::textWidth(buf, scale);              // 58 @scale2
  int x = (gOvX >= 0) ? gOvX : (PANEL_W - w) / 2;
  int y = gOvY;
  if (x < 0) x = 0;
  if (x + w > PANEL_W) x = PANEL_W - w;
  if (y < 0) y = 0;
  if (y + 7 * scale > PANEL_H) y = PANEL_H - 7 * scale;
  // 前景色 + 反色描边（任何背景下都可读；黑字则白描边）
  uint16_t fg = ovFGColor();
  uint16_t ol = ~fg;
  Pix::drawText(gDsp, x - 1, y,     buf, ol, scale);
  Pix::drawText(gDsp, x + 1, y,     buf, ol, scale);
  Pix::drawText(gDsp, x,     y - 1, buf, ol, scale);
  Pix::drawText(gDsp, x,     y + 1, buf, ol, scale);
  Pix::drawText(gDsp, x,     y,     buf, fg, scale);
  // 秒进度条（62..63）
  int sw = (sec + 1) * PANEL_W / 60;
  dspFillRect(0, 62, PANEL_W, 2, 0x0000);
  dspFillRect(0, 62, sw,     2, 0xFFE0);
}

// blit 一帧 RGB565 小端数据到面板
static void blitFrame(const uint8_t* src) {
  for (int y = 0; y < PANEL_H; ++y) {
    const uint8_t* row = src + (uint32_t)y * PANEL_W * 2;
    for (int x = 0; x < PANEL_W; ++x) {
      uint16_t c = (uint16_t)row[x * 2] | ((uint16_t)row[x * 2 + 1] << 8);
      dspDrawPixel(x, y, c);
    }
  }
}

void FaceRemoteImpl::render() {
  if (!gDsp) return;
  if (!gValid) {
    // 还没有收到过表盘：显示推送提示
    gDsp->fillScreen(0x0000);
    Pix::drawText(gDsp, 4, 20, "PUSH FACE", 0x07E0, 2);
    Pix::drawText(gDsp, 4, 40, "FROM APP", 0x07FF, 2);
    return;
  }
  static uint8_t sLastIdx = 0xFF;
  if (gAnimFrames >= 2) {
    // ---- 动画背景模式 ----
    uint8_t idx = gAnimIdx;
    if (gAnimBurst && sOvValid) {
      // 整分钟触发：分钟的第 0 秒启动爆发序列，按 fps 快速播放
      // （9 帧 @8fps ≈ 1.1s 播完），其余时间停最后一帧（待机）。
      // 帧布局：0..frames-2 = 爆发序列，frames-1 = 待机（马里奥跳顶金币 10 帧版）。
      // （v0.3.12 修复：旧版按"秒"逐帧推进 = 1fps，跳跃被拉成逐帧慢动作 → 用户观感"很卡"。）
      uint32_t t = sOvEpoch + 8UL * 3600UL;          // UTC+8
      int      s = (int)(t % 60);
      uint8_t  burstLen = (uint8_t)(gAnimFrames - 1);
      uint8_t  fps = gAnimFps ? gAnimFps : 8;
      static int      sLastSec = -1;
      static uint32_t sBurstMs = 0;                  // 0 = 未在爆发窗口内
      uint32_t nowMs = millis();
      if (s != sLastSec) {
        sLastSec = s;
        if (s == 0) sBurstMs = nowMs;                // 整分钟：启动爆发
      }
      if (sBurstMs && (uint32_t)(nowMs - sBurstMs) < (uint32_t)burstLen * 1000u / fps) {
        uint32_t k = (uint32_t)(nowMs - sBurstMs) * fps / 1000u;
        idx = (k < burstLen) ? (uint8_t)k : (uint8_t)(burstLen - 1);
      } else {
        idx = (uint8_t)(gAnimFrames - 1);            // 待机帧
      }
    }
    blitFrame(animFrame(idx));
    if (gAnimOverlay) drawOverlayClock();
    if (sLastIdx != idx) {
      sLastIdx = idx;
      Serial.printf("[DBG] anim frame %u/%u\n", idx, gAnimFrames);
    }
    return;
  }
  sLastIdx = 0xFF;
  // ---- 单帧模式（BLE/HTTP 单帧推送）----
  static bool sDbgBlit = false;
  blitFrame(gBuf);
  if (gAnimOverlay) drawOverlayClock();   // 单帧也允许叠加时钟
  if (!sDbgBlit) {
    sDbgBlit = true;
    Serial.printf("[DBG] render blit done  px(0,0)=%04X\n",
                  (uint16_t)gBuf[0] | ((uint16_t)gBuf[1] << 8));
  }
}

// ---------------- LittleFS 持久化 ----------------
// 文件：/anim.bin  magic "PAN1" + u8 frames + u8 fps + u8 overlay + u8 burst + 帧数据
// hdr[7]（0.3.x 起）：1 = 整分钟触发模式（burst）

bool saveAnimToFs() {
  if (!gAnimBuf || gAnimFrames < 1) return false;
  File f = LittleFS.open("/anim.bin", "w");
  if (!f) { Serial.println("[ANIM] fs open(w) FAIL"); return false; }
  // hdr 16B：PAN1 + frames + fps + overlay + burst + [mode ox oy ox2 scale fg rsv rsv]
  // 旧版 8B 头（0.3.x 之前）仍可读：按字节数判定，缺省取默认叠加参数
  uint8_t hdr[16] = {'P','A','N','1', gAnimFrames, gAnimFps,
                     (uint8_t)(gAnimOverlay ? 1 : 0),
                     (uint8_t)(gAnimBurst ? 1 : 0),
                     gOvMode, (uint8_t)gOvX, (uint8_t)gOvY, (uint8_t)gOvX2, gOvScale,
                     gOvFG, 0, 0};
  if (f.write(hdr, 16) != 16) { f.close(); return false; }
  size_t n = (size_t)gAnimFrames * FRAME_BYTES;
  if (f.write(gAnimBuf, n) != n) { f.close(); return false; }
  f.close();
  Serial.printf("[ANIM] saved %u frames to /anim.bin (ov mode=%u x=%d y=%d x2=%d sc=%u)\n",
                gAnimFrames, gOvMode, gOvX, gOvY, gOvX2, gOvScale);
  return true;
}

bool hasAnimFs() { return LittleFS.exists("/anim.bin"); }

bool loadAnimFromFs() {
  if (!gAnimBuf && !initAnimBuf()) return false;
  File f = LittleFS.open("/anim.bin", "r");
  if (!f) return false;
  uint8_t hdr[16];
  size_t hn = f.read(hdr, 16);
  if (hn < 8 || memcmp(hdr, "PAN1", 4) != 0) {
    f.close(); Serial.println("[ANIM] fs bad magic"); return false;
  }
  uint8_t frames = hdr[4], fps = hdr[5];
  bool    ov     = hdr[6] != 0;
  bool    burst  = hdr[7] != 0;
  // 叠加参数：16B 新头完整携带；8B 旧头回退默认值
  if (hn >= 16) {
    gOvMode  = hdr[8]  ? 1 : 0;
    gOvX     = (int8_t)hdr[9];
    gOvY     = (int8_t)hdr[10];
    gOvX2    = (int8_t)hdr[11];
    gOvScale = hdr[12] ? hdr[12] : 2;
    gOvFG    = (hdr[13] <= 2) ? hdr[13] : 0;
  } else {
    overlayResetDefaults(0);
  }
  if (frames < 1 || frames > gAnimCap) {
    f.close(); Serial.printf("[ANIM] fs frames=%u > cap=%u\n", frames, gAnimCap);
    return false;
  }
  size_t n = (size_t)frames * FRAME_BYTES;
  if (f.read(gAnimBuf, n) != n) { f.close(); return false; }
  f.close();
  // 同步帧0 到单帧缓冲（BLE commit / 单帧路径一致）
  memcpy(gBuf, gAnimBuf, FRAME_BYTES);
  beginAnim(frames, fps, ov, burst);
  Serial.printf("[ANIM] loaded from fs: %u frames fps=%u overlay=%u burst=%u ovmode=%u\n",
                frames, fps, ov ? 1 : 0, burst ? 1 : 0, gOvMode);
  return true;
}

}  // namespace RemoteFace

// 全局工厂（faces.cpp 注册表约定）
WatchFace* createFaceRemote() {
  static RemoteFace::FaceRemoteImpl f;
  return &f;
}

#endif  // ARDUINO
