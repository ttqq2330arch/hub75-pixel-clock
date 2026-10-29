// ============================================================
//  face_remote.h — BLE 下发的远程表盘（数据驱动渲染）
// ------------------------------------------------------------
//  小程序通过 BLE DATA 特征推送一帧 64x64 RGB565（8192 字节，
//  小端）到 RemoteFace 的帧缓冲；commit 校验 CRC 通过后，
//  本表盘成为可选项（Faces 索引 3），main 循环把它当普通
//  表盘渲染。
//
//  帧缓冲放 DRAM 静态区（8KB，S3 SRAM 512KB 余量充足），
//  不用 PSRAM——HUB75 DMA 每帧都要读它，DRAM 更快更稳。
// ============================================================
#pragma once

#include <stdint.h>
#include "face.h"

#ifdef ARDUINO
class MatrixPanel_I2S_DMA;
#endif

namespace RemoteFace {

// ---- 状态码（BLE STATUS 特征通知用，与小程序约定一致）----
enum Status : uint8_t {
  ST_IDLE      = 0,  // 空闲，无传输
  ST_RECEIVING = 1,  // 正在接收数据块
  ST_OK        = 2,  // 提交成功，已切换到远程表盘
  ST_CRC_FAIL  = 3,  // CRC 校验失败（数据损坏）
  ST_ABORT     = 4,  // 中止 / 接收超时
};

static const uint16_t FRAME_W = 64;
static const uint16_t FRAME_H = 64;
static const uint32_t FRAME_BYTES = FRAME_W * FRAME_H * 2;  // RGB565 = 8192

// ---- 动画背景模式 ----
// 多帧环形播放 + 可选实时时钟叠加（动漫像素时钟）。
// 帧缓冲走 PSRAM（8MB，仅 CPU memcpy 读取，不参与 HUB75 DMA，
// 带宽需求 8KB×fps ≈ 80KB/s，PSRAM 绰绰有余）；PSRAM 不可用时
// 退回普通堆（此时上限降到 MAX_ANIM_FRAMES_SRAM）。
static const uint8_t MAX_ANIM_FRAMES       = 64;    // PSRAM 版上限（512KB）
static const uint8_t MAX_ANIM_FRAMES_SRAM  = 16;    // 普通堆上限（128KB）

// 帧缓冲（extern 供 ble_service / net 直接写）
extern uint8_t  gBuf[FRAME_BYTES];
extern bool     gValid;      // 是否已有一帧完整有效数据
extern uint8_t  gStatus;     // 当前状态码（Status）
extern uint32_t gLastChunkMs;

// 动画状态
extern uint8_t*  gAnimBuf;     // MAX_ANIM_FRAMES × FRAME_BYTES（nullptr = 未分配）
extern uint8_t   gAnimCap;     // 实际可用帧数上限（PSRAM 64 / 堆 16）
extern uint8_t   gAnimFrames;  // 动画帧数（0/1 = 单帧模式，>=2 = 动画模式）
extern uint8_t   gAnimFps;     // 播放帧率 1..30
extern bool      gAnimOverlay; // 是否叠加实时时钟（HH:MM + 秒条）
extern uint8_t   gAnimIdx;     // 当前播放帧序号
extern uint32_t  gAnimLastMs;  // 上次帧推进时刻
extern bool      gAnimBurst;   // 整分钟触发模式：帧 0..N-2 为爆发序列，最后一帧为待机

// ---- 叠加实时时钟的可调参数（随表盘 meta.json 持久化，可经 /dialov 实时调整）----
// mode 0 = 经典 HH:MM（可选前景色 + 反色描边 + 底部秒进度条）
//   x=-1 表示水平居中；y=文本左上角；scale=字号 1..2（"HH:MM" 宽 6*scale-1/字符）
//   fg=0 白 / 1 黑 / 2 黄（浅底表盘用黑，默认白）
// mode 1 = 方块数字（马里奥问号块风格：7x7 大数字，双块布局，固定黑字）
//   (x,y)=小时块左上角，x2=分钟块左上角（块 19x19，数字带在 y+6..y+12）
extern uint8_t gOvMode;    // 0/1
extern int8_t  gOvX;       // mode0: -1=居中；mode1: 小时块 x
extern int8_t  gOvY;       // mode0: 文本 y；mode1: 块 y
extern int8_t  gOvX2;      // mode1: 分钟块 x（mode0 忽略）
extern uint8_t gOvScale;   // mode0 字号 1..2（mode1 忽略，固定 7x7）
extern uint8_t gOvFG;      // mode0 前景色 0=白 1=黑 2=黄（mode1 忽略，固定黑）
// 复位为默认值（mode0 居中 y=46 scale=2 白字 / mode1 块 12,11 与 34,11）
void overlayResetDefaults(uint8_t mode);

// 分配动画缓冲（boot 时调用一次；PSRAM 优先）
bool initAnimBuf();
// 配置并启动动画：分配缓冲、置帧数/帧率/叠加开关，切 REMOTE 由调用方负责。
// burst=true（需 frames>=3）：帧 0..frames-2 在每分钟第 0 秒起逐秒播放，
// 其余时间显示最后一帧（待机）——马里奥整分钟跳顶金币用。
bool beginAnim(uint8_t frames, uint8_t fps, bool overlay, bool burst = false);
// 帧推进（tick 里调用，按 fps 循环）
void animTick(uint32_t nowMs);
// 当前帧指针（render 用）
const uint8_t* animFrame(uint8_t idx);

// ---- LittleFS 持久化（动画存 flash，开机自动播放）----
// 文件格式：magic "PAN1" + u8 frames + u8 fps + u8 overlay + u8 rsv + 原始帧数据
bool saveAnimToFs();      // RAM 动画 → /anim.bin
bool loadAnimFromFs();    // /anim.bin → RAM 并启动（无文件返回 false）
bool hasAnimFs();

// 开始新一帧（清零接收状态，缓冲不动）
void beginRx();
// 写入一个数据块；off/len 越界返回 false
bool writeChunk(uint16_t off, const uint8_t* data, uint16_t len);
// 提交：调用方传入对 gBuf 的 CRC16；匹配则置 gValid 并返回 true
bool commit(uint16_t crc);
// 中止当前传输
void abortRx();
// 接收超时检查（loop 调用）；超时返回 true 并置 ST_ABORT
bool tickTimeout(uint32_t nowMs);
// CRC16-XMODEM（poly 0x1021, init 0x0000）——与小程序侧一致
uint16_t crc16(const uint8_t* data, uint32_t len);

// ---- 表盘对象（faces.cpp 注册用）----
#ifdef ARDUINO
// 远程表盘实现类（face_remote.cpp 定义）
class FaceRemoteImpl : public WatchFace {
public:
  FaceRemoteImpl();
  void onSelect() override;
  void tick(const FaceEnv& env) override;
  void render() override;
};
#endif

}  // namespace RemoteFace

// 全局工厂（faces.cpp 注册表约定，face_remote.cpp 定义）
#ifdef ARDUINO
WatchFace* createFaceRemote();
#endif
