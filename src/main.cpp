// ============================================================
//  main.cpp — HUB75 Pixel Clock 主程序
//  ESP32-S3 + 64x64 HUB75 全彩点阵
//  功能：配网上网 / NTP 时间 / 温湿度 / BLE 接口 / 三表盘
//  交互：BOOT 键短按切表盘，长按 3s 重置 WiFi
// ============================================================
#include <Arduino.h>

#include "config.h"
#include "display_mgr.h"
#include "net.h"
#include "clock_time.h"
#include "sensor.h"
#include "ble_service.h"
#include "face.h"
#include "faces_access.h"
#include "face_remote.h"
#include "font5x7.h"
#include <LittleFS.h>
#include <esp_task_wdt.h>
#include <WiFi.h>               // v0.3.17：WiFi.gatewayIP / WiFiClient（网关通路探测）
#include <esp_bt.h>             // v0.3.17：esp_bt_controller_mem_release（释放经典蓝牙内存）
#include <Preferences.h>
#include <esp_system.h>
#include <soc/rtc_cntl_reg.h>

// ---- BLE+WiFi 共存的关键 hack（v0.3.14 引入，v0.3.18 随 BLE 关闭而停用）----
// Arduino core 的 initArduino()（esp32-hal-misc.c）在 main() 之前执行：
//   #ifdef CONFIG_BT_ENABLED
//       if (!btInUse()) esp_bt_controller_mem_release(ESP_BT_MODE_BTDM);
//   #endif
// btInUse() 是 weak 符号（默认 false）→ setup 前就把整个 BT 控制器内存
// 释放给 WiFi → 之后 BLEDevice::init() 必 abort（PC 0x420c09xx）。
// 解法：用强符号覆盖 weak 的 btInUse，让它返回 true，内存不释放。
// v0.3.18：ENABLE_BLE=0 时不定义强符号 → initArduino 恢复释放 BT 内存
// （省 ~67KB，正是内存枯竭病的最大单项开销）。
#if ENABLE_BLE
extern "C" bool btInUse() { return true; }
#endif

#ifdef ARDUINO

// ------------------------------------------------------------
//  IP 屏显：连上 WiFi / 进入配网模式时在面板上显示 4 秒
// ------------------------------------------------------------
namespace {

uint32_t gIpShowUntil = 0;
char     gIpText[24] = "";
bool     gIpIsAp     = false;

void showIp(const char* ip, bool isAp) {
  snprintf(gIpText, sizeof(gIpText), "%s", ip);
  gIpIsAp = isAp;
  gIpShowUntil = millis() + 10000;   // 4s→10s：留足看全/抄写时间
  Serial.printf("[MAIN] show ip: %s\n", gIpText);
}

void renderIpBanner() {
  if (millis() > gIpShowUntil) return;
  gDsp->fillScreen(0x0000);
  // 5x7 字体每字符 6px，64px 一行最多 10 字符——"192.168.1.52" 有 12 字符
  // 必然截断。按最后一个 '.' 把 IP 拆成两行，各自水平居中。
  int y = 14;
  if (gIpIsAp) { Pix::drawText(gDsp, 11, 4, "AP MODE", 0xFFE0); y = 20; }
  const char* cut = strrchr(gIpText, '.');
  if (cut && cut > gIpText && cut - gIpText <= 15) {
    char top[16];
    int n = (int)(cut - gIpText);
    memcpy(top, gIpText, n); top[n] = '\0';
    Pix::drawText(gDsp, (64 - Pix::textWidth(top)) / 2, y, top, 0x07FF);
    Pix::drawText(gDsp, (64 - Pix::textWidth(cut)) / 2, y + 12, cut, 0x07FF);
  } else {
    int x = (64 - Pix::textWidth(gIpText)) / 2;
    if (x < 0) x = 0;
    Pix::drawText(gDsp, x, y, gIpText, 0x07FF);
  }
  Pix::drawText(gDsp, 14, y + 26, "NET OK", 0x07E0);
}

// ------------------------------------------------------------
//  BOOT 按键：短按切表盘 / 长按 3s 重置 WiFi
// ------------------------------------------------------------
uint32_t gBtnDownAt = 0;
bool     gBtnHeld   = false;
bool     gResetFired = false;

void btnPoll(uint32_t now) {
  bool down = (digitalRead(PIN_BOOT_BTN) == LOW);
  if (down && !gBtnHeld) {
    gBtnHeld    = true;
    gBtnDownAt  = now;
    gResetFired = false;
  } else if (!down && gBtnHeld) {
    gBtnHeld = false;
    uint32_t dur = now - gBtnDownAt;
    if (dur < 800) {                       // 短按：切表盘（循环，跳过 0 号 TEST 图案）
      int n = Faces::gCount;
      int next = FacesAcc::current() + 1;
      if (next >= n) next = (n > 1) ? 1 : 0;   // 绕回时跳过 TEST（0），从时钟(1)开始
      FacesAcc::request(next);
      Serial.printf("[BTN] face -> %d\n", next);
    } else if (dur >= 800 && dur < 3000) {
      // 1~3s：切换配色（仅时钟表盘响应逻辑放这，简化版提示即可）
      Serial.println("[BTN] medium press (reserved)");
    }
  } else if (gBtnHeld && !gResetFired && now - gBtnDownAt > 3000) {
    gResetFired = true;
    Serial.println("[BTN] long press -> reset wifi");
    if (gDsp) {
      gDsp->fillScreen(0x0000);
      Pix::drawText(gDsp, 4, 26, "RESET WIFI", 0xF800, 2);
    }
    Net::reset();
  }
}

// BLE 请求切盘回调
void onBleFace(uint8_t idx) {
  Serial.printf("[BLE] face request %u\n", idx);
  FacesAcc::request(idx);
}

uint32_t gLastFrame = 0;
WatchFace* gActive  = nullptr;
int        gActiveIdx = -1;

void applyFaceIfChanged(int fallbackIdx) {
  int want = (FacesAcc::gDesired >= 0) ? FacesAcc::gDesired
                                       : (gActiveIdx >= 0 ? gActiveIdx : fallbackIdx);
  if (want == gActiveIdx && gActive) return;
  WatchFace* f = Faces::byIndex(want);
  if (!f) return;
  FacesAcc::gCurrent  = want;
  FacesAcc::gDesired  = -1;
  gActive   = f;
  gActiveIdx = want;
  gActive->onSelect();
  Serial.printf("[FACE] %s (%s)\n", f->name(), f->id());
}

}  // namespace

// ---- 主循环看门狗（v0.3.13 重排）----
// 背景：用户上传表盘后板子 ping 通但 HTTP 完全无响应 = loopTask 卡死在
// ESP32 WebServer 的 socket 读里（客户端异常断开时 readString 死等 connected），
// 只能拔电恢复。兜底一（芯片级）：TWDT 订阅 loopTask，卡死 30s → panic 重启。
// v0.3.12 教训：TWDT 原在 setup 中段订阅，而 BLE/动画 init 慢于 10s 即 panic，
// 形成"重启→又超时→再重启"循环（用户报"一直重新启动"）。
// v0.3.13 修正：①订阅挪到 setup 最末尾（所有慢 init 完成后）②超时 10s→30s
// ③禁 brownout（64×64 满亮白屏 5V 冲击触发 brownout 也是重启循环源）
// ④NVS 重启循环保护：30s 内连启 3 次 → 安全模式（只渲染不起 HTTP，可救砖）
// 兜底二（本任务，pin CPU0 与 loopTask 的 CPU1 并行）：心跳停跳 45s → restart；
// 另监控 WiFi 持久掉线（曾连上后持续断 120s，AUTH_EXPIRE 类）→ restart 自愈。
static volatile uint32_t gHeartbeatMs = 0;
static volatile bool     gSafeMode   = false;   // 重启循环保护：只渲染，不起 HTTP/TWDT

static void loopWatchdogTask(void* /*arg*/) {
  static bool     sEverConnected = false;   // 曾连上过才监控掉线（避开 SoftAP 配网模式）
  static uint32_t sWifiDownMs    = 0;
  // ---- v0.3.17：对外通路探测 + 堆监控（fix「HTTP 假死但看门狗全盲」）----
  // 2026-10-26 实测第 4 次假死的完整证据链：HTTP 死、ping 先通后死、串口无
  // 输出、板子自检（回环打自己 IP，lwIP 走本地环回不过射频）通过——
  // 说明 loop 心跳正常、TWDT 喂得好好的，死的是「外部设备↔板子」的射频
  // 通路（WiFi.status() 仍报 connected，三层看门狗全是盲区）。
  // 解法：在本任务（独立于 loop）里每 60s 用 WiFiClient 连一次网关 :80，
  // 走真实射频路径；连续 5 次超时失败 → 判定通路死透 → 重启自愈。
  // 另：每 60s 查 free heap，<50KB（资源泄漏）也重启；每 5 分钟打健康快照。
  static uint32_t sLastProbeMs = 0;
  static uint8_t  sLogDiv      = 0;
  static uint8_t  sHeapLowRuns = 0;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(5000));
    if (gSafeMode) continue;                // 安全模式：不自动重启，等用户介入
    // ① loopTask 心跳停跳 >45s → 重启
    uint32_t hb = gHeartbeatMs;                  // 32 位对齐读，原子
    if (hb && (millis() - hb) > 45000) {         // 无符号差，天然处理 millis 回绕
      Serial.printf("[WDT] loop stalled %us -> restart\n",
                    (unsigned)((millis() - hb) / 1000));
      Serial.flush();
      vTaskDelay(pdMS_TO_TICKS(50));
      ESP.restart();
    }
    // ② WiFi 曾连上后持续断开 >120s → 重启（ping 通但 TCP 死的持久掉线）
    if (Net::staConnected()) {
      sEverConnected = true;
      sWifiDownMs    = 0;
      // ③ 对外通路探测 + 堆监控（60s 一轮）
      if (millis() - sLastProbeMs > 60000) {
        sLastProbeMs = millis();
        uint32_t heapNow = ESP.getFreeHeap();
        // 堆监控（v0.3.17 修正）：实测基线 ~16KB（BLE+WiFi+HUB75 常态），
        // 50KB 阈值会误杀成重启循环（14:47 教训）。改为：<20KB 只记日志；
        // 连续 3 轮 <6KB（≈3 分钟持续枯竭，lwIP 必然开不出 socket）才重启。
        if (heapNow < 20000) {
          Serial.printf("[WDT] heap low %uB (below 20KB, logging)\n", (unsigned)heapNow);
        }
        if (heapNow < 6000) {
          if (++sHeapLowRuns >= 3) {
            Serial.printf("[WDT] heap <6KB x3 runs -> restart\n");
            Serial.flush();
            vTaskDelay(pdMS_TO_TICKS(50));
            ESP.restart();
          }
        } else {
          sHeapLowRuns = 0;
        }
        // v0.3.18：网关 TCP 探测【已停用并删除】。理由：① 与 net.cpp 的 HTTP
        // 自检功能重复；② 从 WDT 任务连 socket 和 loopTask 的 WebServer/自检
        // 并发，是 10-26「~90s 后 HTTP 停止服务」的最大嫌疑扰动源（v0.3.13
        // 无它时可稳跑数日）。对外通路死活由 net.cpp 自检兜底（10s×5 次）。
        // 如需恢复，git/日志里有完整实现（gateway probe，连败 5 次→重启）。
        // v0.3.17：每轮都打堆曲线（15:32 实测堆会在几分钟内跌到 5KB 级，
        // 每条日志带 uptime 才能把「泄漏速率」和事件对上，定位枯竭源头）
        Serial.printf("[WDT] heap=%u rssi=%d up=%us\n",
                      (unsigned)heapNow, WiFi.RSSI(), (unsigned)(millis() / 1000));
      }
    } else if (sEverConnected) {
      if (!sWifiDownMs) sWifiDownMs = millis();
      else if (millis() - sWifiDownMs > 120000) {
        Serial.println("[WDT] wifi down 120s -> restart");
        Serial.flush();
        vTaskDelay(pdMS_TO_TICKS(50));
        ESP.restart();
      }
    }
  }
}

// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.printf("\n[HUB75-PIXELCLOCK] v%s\n", FW_VERSION);

  // v0.3.14：BLE 必须在任何 WiFi init 之前初始化。
  // esp_bt_controller_enable 内部的 coex_enable/coex_core_enable 在 WiFi 先
  // init 的情况下直接 abort()（backtrace 实测：coex_core_enable ← coex_enable
  // ← esp_bt_controller_enable ← btStart ← BLEDevice::init ← Ble::begin）。
  // 顺序：BT 先注册 coex adapter，WiFi 后 init 幂等复用，共存才不崩。
  // （btInUse 强符号覆盖已解决"initArduino 提前释放 BT 控制器内存"问题。）
#if ENABLE_BLE
  // v0.3.17：只用 BLE 不用蓝牙经典(BR/EDR)——提前释放经典蓝牙控制器内存。
  // 实测 heap 基线仅 ~16KB（BLE+WiFi+HUB75 常态），枯竭时 lwIP 开不出
  // socket = 「外部访问全死」假死的真正根源，能省一点是一点。
  Serial.printf("[SYS] heap before BT trim: %u\n", (unsigned)ESP.getFreeHeap());
  esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
  Serial.printf("[SYS] heap after  BT trim: %u\n", (unsigned)ESP.getFreeHeap());
  Ble::begin(onBleFace);
  Serial.printf("[SYS] heap after BLE: %u\n", (unsigned)ESP.getFreeHeap());
#endif

  pinMode(PIN_BOOT_BTN, INPUT_PULLUP);

  // ---- v0.3.13: 禁 brownout detector ----
  // 64×64 满亮白屏瞬时电流大，USB/5V 输入跌落会触发 brownout 直接复位，
  // 表现为"一直重新启动"。HUB75 全亮项目常规操作（画面偶发花屏也比
  // 无限重启好；真电源不足靠加大供电解决，不靠 detector 拖垮系统）。
  // ESP32-S3：清 RTC_CNTL_BROWN_OUT_ENA(BIT30) 关闭 brownout detector
  CLEAR_PERI_REG_MASK(RTC_CNTL_BROWN_OUT_REG, RTC_CNTL_BROWN_OUT_ENA);
  Serial.println("[SYS] brownout detector disabled");

  // ---- v0.3.13: 重启循环保护（NVS 计数）----
  // 若 setup 中途被 TWDT/异常反复干掉（30s 内连启 ≥3 次），进安全模式：
  // 只渲染时钟、不起 HTTP、不订 TWDT——保证屏幕有画面、系统不再自重启，
  // 用户可拔电或走串口介入。稳定运行 60s 后计数自动清零，下次启动恢复。
  {
    Preferences sysPrefs;
    sysPrefs.begin("sys", false);
    uint32_t bootCnt = sysPrefs.getUInt("bootcnt", 0) + 1;
    sysPrefs.putUInt("bootcnt", bootCnt);
    sysPrefs.end();
    if (bootCnt >= 3) {
      gSafeMode = true;
      Serial.printf("[SAFE] rapid reboot x%u -> safe mode (HTTP/WDT off)\n", bootCnt);
    }
  }

  // 1) 面板：先点亮，黑屏作为兜底
  if (Display::begin() != 0) {
    Serial.println("[FATAL] panel init failed, halt");
    while (true) delay(1000);
  }
  Serial.printf("[SYS] heap after Display(DMA): %u\n", (unsigned)ESP.getFreeHeap());

  // 安全模式提示（须在面板 init 后，否则 gDsp 为空画不出来）
  if (gSafeMode) {
    gDsp->fillScreen(0x0000);
    Pix::drawText(gDsp, 4, 24, "SAFE MODE", 0xF800, 2);
    Pix::drawText(gDsp, 4, 44, "POWER CYCLE", 0xFFE0, 1);
    delay(3000);   // 停留 3s 让用户看清；之后时钟渲染循环照常继续
  }

  // 2) 基础服务
  Sensor::begin();
  // 动画背景：PSRAM 帧缓冲 + flash 持久化（先分配，boot 才能自动播放）
  if (!LittleFS.begin(true)) {
    Serial.println("[FS] LittleFS mount FAIL (anim persistence off)");
  } else {
    Serial.printf("[FS] LittleFS ok, total=%uKB used=%uKB\n",
                  (unsigned)(LittleFS.totalBytes() / 1024),
                  (unsigned)(LittleFS.usedBytes() / 1024));
  }
  RemoteFace::initAnimBuf();
  Serial.printf("[SYS] heap after FS/anim: %u\n", (unsigned)ESP.getFreeHeap());
  if (!gSafeMode) {
    Net::begin("PixelClock-Setup", showIp);
    Net::setFaceSelect(onBleFace);   // HTTP 推表盘也复用同一切盘回调
  }
  ClockT::begin();
  Serial.printf("[SYS] heap after Net/NTP: %u\n", (unsigned)ESP.getFreeHeap());

  // 3) 表盘注册
  Faces::registerBuiltins();
  if (RemoteFace::loadAnimFromFs()) {
    // flash 里存过动画背景 → 开机直接播放（动漫像素时钟）
    // （15:44 泄漏对照实验已结束：动画洗清嫌疑，真凶是 BLE+WiFi 共存开销，恢复自动播放）
    FacesAcc::request(FACE_IDX_REMOTE);
    Serial.println("[MAIN] boot: animation from flash");
  }
  applyFaceIfChanged(1);   // 默认像素时钟

  gLastFrame = millis();

  // ---- v0.3.13: TWDT 订阅挪到 setup 最末尾 ----
  // 必须等所有慢初始化（Net/BLE/FS/动画）跑完再订阅，否则 loopTask 只是
  // 在 setup 里正常干活也会被 10s 超时 panic 成重启循环（v0.3.12 的坑）。
  if (!gSafeMode) {
    esp_task_wdt_deinit();          // 清掉 core 默认配置（可能只订了 idle 任务）
    {
      // 本框架 IDF 为旧版 API：esp_task_wdt_init(timeout, panic)（无 config 结构体）
      esp_err_t e1 = esp_task_wdt_deinit();          // 双保险：再清一次
      esp_err_t e2 = esp_task_wdt_init(30000, true); // 30s 超时，panic 重启（串口留 backtrace）
      esp_err_t e3 = esp_task_wdt_add(NULL);         // NULL = 当前任务 = loopTask
      Serial.printf("[WDT] twdt deinit=%s init=%s add=%s (loopTask, 30s)\n",
                    esp_err_to_name(e1), esp_err_to_name(e2), esp_err_to_name(e3));
    }
  }
  {
    TaskHandle_t wd = nullptr;
    BaseType_t  ok = xTaskCreatePinnedToCore(loopWatchdogTask, "loopwd", 2048,
                                             nullptr, 1, &wd, 0);
    Serial.printf("[WDT] monitor task create=%d handle=%p\n", (int)ok, (void*)wd);
  }
}

void loop() {
  uint32_t now = millis();
  gHeartbeatMs = now;       // 看门狗心跳：必须在任何可能阻塞的调用（Net::loop 等）之前更新
  if (!gSafeMode) esp_task_wdt_reset();   // 喂 TWDT（芯片级 loopTask 看门狗）

  // 稳定运行 60s → 清重启计数（离开安全模式的前提；下次启动恢复正常模式）
  static bool sBootCntCleared = false;
  if (!sBootCntCleared && now > 60000) {
    sBootCntCleared = true;
    Preferences p;
    p.begin("sys", false);
    if (p.getUInt("bootcnt", 0) != 0) {
      p.putUInt("bootcnt", 0);
      Serial.println("[SAFE] stable 60s, boot count cleared");
    }
    p.end();
  }

  // ---- 服务轮询 ----
  if (!gSafeMode) Net::loop();
  ClockT::loop();
#if ENABLE_BLE
  Ble::loop();
#endif
  Display::tickDim(ClockT::epoch());
  Display::loop(now);
  btnPoll(now);
  applyFaceIfChanged(1);

  // ---- 帧生成（~30fps 上限，肉眼足够，省 CPU 给 WiFi/BLE）----
  if (now - gLastFrame < 33) return;
  gLastFrame = now;

  if (millis() < gIpShowUntil) {
    renderIpBanner();
  } else if (gActive) {
    FaceEnv env;
    env.nowMs      = now;
    env.nowEpoch   = ClockT::epoch();
    env.epochValid = ClockT::valid();
    if (!Sensor::read(env.tempC, env.humi)) { env.tempC = NAN; env.humi = NAN; }
    gActive->tick(env);
    gActive->render();   // 按 WatchFace 接口契约每帧调用 render()：
                         // 远程表盘(RemoteFace)的绘制全在 render() 里，
                         // 不调它推上去的表盘就不会被画到面板（之前全黑的根因）
  }

  if (gDsp) gDsp->flipDMABuffer();   // 双缓冲原子交换，无撕裂
}

#endif  // ARDUINO
