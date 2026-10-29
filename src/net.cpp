// ============================================================
//  net.cpp — WiFi STA + SoftAP 配网门户
// ------------------------------------------------------------
//  关键坑备忘（来自 esp32-webui-wifi-hold skill 实战）：
//  1. WiFi.persistent(false)——防协议栈自己往 NVS 写导致 flash 磨损
//  2. 门户 WebServer 在 softAP 起来之后 begin()；STA 模式下
//     softAP 协议栈同样已创建，两者都不碰 LwIP 未初始化断言
//  3. 凭据只存 NVS(Preferences)，配置页不回显已存密码
//  4. DNSServer 劫持全部域名 → 手机连上自动弹门户
//  5. 连上后在屏上显示 IP（mDNS 在 Windows 要 Bonjour，不指望）
// ============================================================
#include "net.h"
#include "config.h"
#include "face_remote.h"
#include "display_mgr.h"   // 屏幕亮度控制（Display::setBrightness / brightness）

#ifdef ARDUINO

#include <WiFi.h>
#include <esp_wifi.h>      // v0.3.14：esp_wifi_set_ps（共存休眠模式）
#include <DNSServer.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <LittleFS.h>
#include <cctype>
#include "faces_web.h"   // 网页版表盘推送器（自动生成，PROGMEM）
#include "push_page_gz.h"  // 首页 gzip 成品（96KB→13.4KB，弱信号 8s→1s）
#include "faces_data.h"    // v0.3.15：表盘商店(FACES)全量含预览，gzip 后由 /faces 端点按需下发

namespace Net {

namespace {

enum Mode { MODE_IDLE, MODE_STA, MODE_PORTAL, MODE_PORTAL_DONE };
Mode gMode = MODE_IDLE;

IPAddress gIp;
ShowIpFn  gShowIp = nullptr;
const char* gApName = "PixelClock";

Preferences gPrefs;
WebServer   gSrv(80);
DNSServer   gDns;
bool        gServerUp = false;
FaceSelectFn gFaceSel = nullptr;

uint32_t gStaDeadline = 0;   // STA 尝试截止（ms）
const uint32_t STA_TIMEOUT = 15000;

// WiFi 看门狗：路由器周期性 AUTH_EXPIRE 掉线后必须自动重连，
// 否则掉一次就永久失联（0.2.x 的真实事故：屏幕还亮着但 IP 已死）
uint32_t gDownSince = 0;     // 断连起始时刻（0 = 在线）
bool     gMdnsUp    = false;

// ---------- v0.3.16：HTTP 服务自检（TCP 假死自动重启）----------
// 症状（2026-10-26 实测 3 次）：WL_CONNECTED 一切正常、ping 通，
// 但 80 端口不再应答 TCP，串口无崩溃日志——WebServer/lwIP 服务侧假死。
// 现有看门狗只盯 WiFi.status()，对这种"连着但死了"是盲区。
// 方案：板子每 90s 回环请求自己的 /status（异步两段式：connect+发送在本次
// loop，响应在后续 loop 里查——单线程下不能阻塞等回复）。连续 3 次失败
// （connect 被拒或 3s 无响应）→ 判定服务假死 → 软重启自愈。
// 误报保护：3 次连续才动手；WebServer 对不发数据的 stale client 有 ~5s
// 超时，单次阻塞不会凑满连续 3 次。重启风暴由既有 safe-mode bootcnt 兜底。
WiFiClient gProbe;              // 回环探测连接
uint32_t   gProbeSentAt = 0;    // 请求已发出时刻（0 = 无在途探测）
uint8_t    gProbeFails = 0;     // 连续失败计数（成功即清零）
uint32_t   gLastProbeMs = 0;    // 上次探测启动时刻
const uint32_t PROBE_PERIOD_MS = 300000;   // v0.3.18：90s→300s。90s 太密，和真实客户端
                                           // （手机/浏览器轮询）挤车，误判成服务假死
const uint32_t PROBE_TIMEOUT_MS = 10000;   // 3s→10s：WebServer 清一个僵尸客户端最长 5s，
                                           // 3s 超时会假阳性（10-26 复盘：重启循环真凶之一）
const uint8_t  PROBE_MAX_FAILS = 5;        // 3→5 次：重启从 4.5min 放宽到 ~25min，纯兜底

void probeRestart(const char* why) {
  Serial.printf("[NET] self-check: %s -> HTTP server stalled, soft restart\n", why);
  delay(200);                    // 给串口留刷出去的时间
  ESP.restart();
}

void httpSelfCheck() {           // 仅 MODE_IDLE（STA 已连）分支调用
  if (gProbeSentAt) {            // ---- 在途探测：等响应 ----
    if (gProbe.available()) {    // 服务端回话了 = HTTP 活着
      while (gProbe.available()) gProbe.read();
      gProbe.stop();
      if (gProbeFails) Serial.printf("[NET] self-check recovered (was fail x%u)\n", gProbeFails);
      gProbeFails = 0;
      gProbeSentAt = 0;
      gLastProbeMs = millis();
      return;
    }
    if (millis() - gProbeSentAt > PROBE_TIMEOUT_MS) {   // 3s 无响应
      gProbe.stop();
      gProbeSentAt = 0;
      if (++gProbeFails >= PROBE_MAX_FAILS) probeRestart("no reply 3s");
      else Serial.printf("[NET] self-check FAIL #%u (no reply)\n", gProbeFails);
      gLastProbeMs = millis();
    }
    return;
  }
  if (millis() - gLastProbeMs < PROBE_PERIOD_MS) return;    // 未到周期
  gLastProbeMs = millis();
  if (WiFi.status() != WL_CONNECTED || gIp[0] == 0) return; // 网络没好不测
  if (gProbe.connect(gIp, 80)) {
    gProbe.print("GET /status HTTP/1.0\r\n\r\n");
    gProbeSentAt = millis();
  } else {                     // 连自己 80 都被拒 = 服务假死
    if (++gProbeFails >= PROBE_MAX_FAILS) probeRestart("connect refused");
    else Serial.printf("[NET] self-check FAIL #%u (connect refused)\n", gProbeFails);
  }
}

// 主机名（mDNS + DHCP 主机名）：默认 "pixelclock"，可被 LittleFS /hostname.txt 覆盖。
// 多板部署时给每块板起独立名字（pixelclock-01 / pixelclock-02 ...）以避免 mDNS 抢名。
String   gHostname  = "pixelclock";

// ---------- 门户页面（PROGMEM，不占堆）----------
const char PORTAL_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>像素时钟 配网</title>
<style>
body{background:#111;color:#eee;font-family:sans-serif;margin:0;padding:24px}
h1{font-size:20px;color:#ffb000}
label{display:block;margin:14px 0 6px;color:#aaa;font-size:13px}
input{width:100%;box-sizing:border-box;padding:10px;border:1px solid #444;
border-radius:8px;background:#1c1c1c;color:#fff;font-size:15px}
button{margin-top:20px;width:100%;padding:12px;border:0;border-radius:8px;
background:#ffb000;color:#111;font-size:16px;font-weight:bold}
.tip{margin-top:16px;font-size:12px;color:#666;line-height:1.6}
</style></head><body>
<h1>◈ 像素时钟 — 配网</h1>
<form method="POST" action="/save">
<label>WiFi 名称（SSID）</label><input name="ssid" maxlength="32" required>
<label>WiFi 密码</label><input name="pass" type="password" maxlength="63">
<button type="submit">保存并连接</button>
</form>
<p class="tip">保存后设备自动重启并连接该 WiFi。<br>
连接成功后面板会显示 IP 地址。<br>
之后时间将通过 NTP 自动同步。</p>
</body></html>
)rawliteral";

const char SAVED_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>已保存</title>
<style>body{background:#111;color:#0f8;font-family:sans-serif;
text-align:center;padding:60px 24px}span{color:#666;font-size:13px}</style>
</head><body><h1>✓ 已保存</h1><p>设备正在重启…</p><span>5 秒后可关闭本页面</span>
</body></html>
)rawliteral";

String htmlEscape(const String& s) {
  String o; o.reserve(s.length() + 8);
  for (size_t i = 0; i < s.length(); ++i) {
    char c = s[i];
    if (c == '&') o += "&amp;";
    else if (c == '<') o += "&lt;";
    else if (c == '>') o += "&gt;";
    else if (c == '"') o += "&quot;";
    else o += c;
  }
  return o;
}

// ---------- 凭据 ----------
bool loadCreds(String& ssid, String& pass) {
  gPrefs.begin("netcfg", true);              // 只读
  ssid = gPrefs.getString("ssid", "");
  pass = gPrefs.getString("pass", "");
  uint8_t r = gPrefs.getUChar("rot", 0);     // v0.3.22：开机恢复屏幕旋转角度
  gPrefs.end();
  gRot = (r < 4) ? r : 0;
  return ssid.length() > 0;
}

void saveCreds(const String& ssid, const String& pass) {
  gPrefs.begin("netcfg", false);
  gPrefs.putString("ssid", ssid);
  gPrefs.putString("pass", pass);
  gPrefs.end();
}

// 从 LittleFS /hostname.txt 载入主机名（多板部署用）。文件不存在/非法则用默认 "pixelclock"。
void loadHostname() {
  if (!LittleFS.begin()) { gHostname = "pixelclock"; return; }
  if (!LittleFS.exists("/hostname.txt")) { gHostname = "pixelclock"; return; }
  File f = LittleFS.open("/hostname.txt", "r");
  if (!f) { gHostname = "pixelclock"; return; }
  String s = f.readString();
  f.close();
  s.trim();
  if (s.length() == 0 || s.length() > 31) { gHostname = "pixelclock"; return; }
  for (char c : s) {
    if (!isalnum((unsigned char)c) && c != '-') { gHostname = "pixelclock"; return; }
  }
  gHostname = s;
  Serial.printf("[NET] hostname = %s (from /hostname.txt)\n", gHostname.c_str());
}

// 网页设主机名：POST /setname?name=pixelclock-02 → 写 /hostname.txt 并重启
void handleSetName() {
  String name = gSrv.arg("name");
  name.trim();
  if (name.length() == 0 || name.length() > 31) {
    gSrv.send(400, "text/plain; charset=utf-8", "bad name length");
    return;
  }
  for (char c : name) {
    if (!isalnum((unsigned char)c) && c != '-') {
      gSrv.send(400, "text/plain; charset=utf-8", "bad name: only a-z 0-9 -");
      return;
    }
  }
  if (!LittleFS.begin()) { gSrv.send(500, "text/plain; charset=utf-8", "fs error"); return; }
  File f = LittleFS.open("/hostname.txt", "w");
  if (!f) { gSrv.send(500, "text/plain; charset=utf-8", "write error"); return; }
  f.print(name);
  f.close();
  String msg = "hostname set to " + name + ", rebooting...";
  Serial.printf("[NET] %s\n", msg.c_str());
  gSrv.send(200, "text/plain; charset=utf-8", msg);
  delay(600);
  ESP.restart();
}

// ---------- 门户 ----------
void handleRoot() {
  // 已存 SSID 可提示（不回显密码）
  String ssid, pass;
  gPrefs.begin("netcfg", true);
  ssid = gPrefs.getString("ssid", "");
  gPrefs.end();
  String page = FPSTR(PORTAL_PAGE);
  if (ssid.length()) {
    page.replace("<h1>", "<h1>当前已配置：" + htmlEscape(ssid) + "<br>");
  }
  gSrv.send(200, "text/html; charset=utf-8", page);
}

void handleSave() {
  if (gSrv.args() < 2) { gSrv.send(400, "text/plain", "bad request"); return; }
  String ssid = gSrv.arg("ssid");
  String pass = gSrv.arg("pass");
  ssid.trim();
  if (!ssid.length() || ssid.length() > 32) {
    gSrv.send(400, "text/plain", "ssid invalid"); return;
  }
  saveCreds(ssid, pass);
  gSrv.send(200, "text/html; charset=utf-8", SAVED_PAGE);
  delay(800);
  ESP.restart();
}

void handleNotFound() {
  gSrv.sendHeader("Location", "/", true);
  gSrv.send(302, "text/plain", "");
}

void handleStatus();   // 前向声明（定义见 startSta 之后）
void handleBrightnessGet();   // 屏幕亮度：GET 当前值
void handleBrightnessSet();   // 屏幕亮度：POST 设置
void handleRotate();          // 屏幕旋转：GET 循环切换 / POST ?v=0..3 指定（v0.3.22）
void handleWifiGet();         // WiFi 切换：GET 当前 SSID（不回显密码）（v0.3.23）
void handleWifiSet();         // WiFi 切换：POST ssid&pass → 保存重启，失败自动回门户（v0.3.23）
void handleDialUp();      // FS 表盘库：分片上传
void handleDialList();    // FS 表盘库：列表
void handleDialPreview(); // FS 表盘库：首帧 base64 缩略图
void handleDialPlay();    // FS 表盘库：载入播放
void handleDialOv();      // FS 表盘库：叠加层位置/模式实时调整
void handleDialDel();     // FS 表盘库：删除（.rgb565 + .json）
void handleFaces();       // 表盘商店：GET /faces → FACES 全量（含预览）gzip JSON

// ---------- 网页版推送器（STA 模式主页）----------
// v0.3.13：发 gzip 成品（PUSH_PAGE_GZ，13.4KB）+ Content-Encoding: gzip，
// 浏览器自动解压。原来直发 96KB PUSH_PAGE，弱信号 WiFi 下要 8s+，
// 用户感知"网页打不开"（实际是慢）。
// 发送方式：memcpy_P 分块拷进 RAM 再 sendContent（绕开 send_P 二进制路径，
// 该路径在 core 2.0.17 上对含 \0 的 PROGMEM 二进制无响应）。改模板后需重跑
// tools/gen_faces_web.py + tools/gen_push_page_gz.py 再编译。
void handleHome() {
  gSrv.sendHeader("Content-Encoding", "gzip");
  gSrv.setContentLength(PUSH_PAGE_GZ_LEN);
  gSrv.send(200, "text/html; charset=utf-8", "");
  // 一次发全量：WiFiClient::write 内部 select 粒度 1s×10 次重试，分块越小
  // 等待叠加越久（1KB×14 块实测 >10s）。13.4KB 一次交给 lwIP 缓冲批量发送
  // （旧版 96KB 一次 send_P 8s 即此机制）。缓冲必须 static：loop 栈仅 8KB。
  static uint8_t buf[PUSH_PAGE_GZ_LEN];
  memcpy_P(buf, PUSH_PAGE_GZ, PUSH_PAGE_GZ_LEN);
  gSrv.sendContent((const char*)buf, PUSH_PAGE_GZ_LEN);
}

// 表盘商店：GET /faces → FACES 全量（含预览 d）gzip JSON。
// v0.3.15：首页不再内嵌预览（控制面板精简到 <5KB，MIN_MODEM 下稳定加载），
// 此处按需下发，前端带重试拉取；传输失败不影响主控制面板（只少了预览图）。
void handleFaces() {
  gSrv.sendHeader("Content-Encoding", "gzip");
  gSrv.setContentLength(FACE_DICT_GZ_LEN);
  gSrv.send(200, "application/json", "");
  static uint8_t buf[FACE_DICT_GZ_LEN];   // static：loop 任务栈仅 8KB，不能放大缓冲
  memcpy_P(buf, FACE_DICT_GZ, FACE_DICT_GZ_LEN);
  gSrv.sendContent((const char*)buf, FACE_DICT_GZ_LEN);
}

// 切换固件内置表盘：POST /face?idx=0..3（0=TEST 1=CLOCK 2=PLASMA 3=REMOTE）
void handleFace() {
  if (!gSrv.hasArg("idx")) { gSrv.send(400, "text/plain", "need idx"); return; }
  int idx = gSrv.arg("idx").toInt();
  if (idx < 0 || idx > 3)  { gSrv.send(400, "text/plain", "idx 0..3"); return; }
  if (gFaceSel) gFaceSel((uint8_t)idx);
  gSrv.send(200, "text/plain", "FACE " + String(idx));
}

// ---------- HTTP 推表盘（M3 验证通道，绕开 BLE）----------
//   分块 POST：/pushface?off=N&len=M  body=该块的 HEX 文本（无 \0，规避二进制截断）
//   提交：    /pushface?commit=1       —— 内部对整帧算 CRC16-XMODEM 后提交
//   整帧 POST：/pushface  body=完整 16384 字符 HEX（可选，自动提交）
//   说明：ESP32 WebServer 的 arg("plain") 会把含 0x00 的二进制 body 当 C 串截断，
//        故统一用 HEX 文本传输，服务端解码写入 gBuf。
static uint8_t hexVal(char c) {
  if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
  if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
  if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
  return 0;
}

void handlePushFace() {
  if (gSrv.hasArg("commit")) {
    uint16_t crc = RemoteFace::crc16(RemoteFace::gBuf, RemoteFace::FRAME_BYTES);
    if (RemoteFace::commit(crc)) {
      Serial.println("[HTTP] face committed, switching to REMOTE");
      if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
      gSrv.send(200, "text/plain", "COMMIT OK");
    } else {
      gSrv.send(400, "text/plain", "CRC FAIL");
    }
    return;
  }

  // body 为 HEX 文本（偶数长度，无 \0）
  String body = gSrv.arg("plain");
  uint16_t hexLen = body.length();
  if (hexLen % 2 != 0) { gSrv.send(400, "text/plain", "bad hex len"); return; }
  uint16_t nbytes = hexLen / 2;

  uint16_t off = gSrv.hasArg("off") ? (uint16_t)gSrv.arg("off").toInt() : 0;
  uint32_t bound = RemoteFace::gAnimBuf
      ? (uint32_t)RemoteFace::gAnimCap * RemoteFace::FRAME_BYTES
      : RemoteFace::FRAME_BYTES;
  if ((uint32_t)off + nbytes > bound) {
    gSrv.send(400, "text/plain", "overflow");
    return;
  }
  if (off == 0) RemoteFace::beginRx();
  for (uint16_t i = 0; i < nbytes; ++i) {
    uint8_t b = (uint8_t)((hexVal(body[i * 2]) << 4) | hexVal(body[i * 2 + 1]));
    uint32_t p = (uint32_t)off + i;
    if (p < RemoteFace::FRAME_BYTES) {
      RemoteFace::gBuf[p] = b;                              // 帧0：单帧路径
      if (RemoteFace::gAnimBuf) RemoteFace::gAnimBuf[p] = b; // 同步动画区
    } else if (RemoteFace::gAnimBuf) {
      RemoteFace::gAnimBuf[p] = b;                          // 帧1..N：动画区
    }
  }
  RemoteFace::gStatus      = RemoteFace::ST_RECEIVING;
  RemoteFace::gLastChunkMs = millis();

  if (!gSrv.hasArg("off") && nbytes == RemoteFace::FRAME_BYTES) {  // 整帧一步到位
    uint16_t crc = RemoteFace::crc16(RemoteFace::gBuf, RemoteFace::FRAME_BYTES);
    if (RemoteFace::commit(crc)) {
      Serial.println("[HTTP] face committed, switching to REMOTE");
      if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
      gSrv.send(200, "text/plain", "COMMIT OK");
    } else {
      gSrv.send(400, "text/plain", "CRC FAIL");
    }
    return;
  }
  gSrv.send(200, "text/plain", "CHUNK " + String(off) + "+" + String(nbytes));
}

// ---------- 动画背景（多帧 + 实时时钟叠加）----------
// 启动：POST /anim?frames=N&fps=F&overlay=0|1[&burst=0|1]
//       叠加层参数（可选）：ovmode=0|1&ox=&oy=&ox2=&ovs=
void handleAnim() {
  if (!gSrv.hasArg("frames")) { gSrv.send(400, "text/plain", "need frames"); return; }
  int frames = gSrv.arg("frames").toInt();
  int fps    = gSrv.hasArg("fps")    ? gSrv.arg("fps").toInt()    : 10;
  int ov     = gSrv.hasArg("overlay") ? gSrv.arg("overlay").toInt() : 1;
  int burst  = gSrv.hasArg("burst")  ? gSrv.arg("burst").toInt()  : 0;
  if (!RemoteFace::beginAnim((uint8_t)frames, (uint8_t)fps, ov != 0, burst != 0)) {
    gSrv.send(500, "text/plain", "ANIM BUF FAIL");
    return;
  }
  // 叠加层模式/位置（不传则维持当前值）
  if (gSrv.hasArg("ovmode")) RemoteFace::gOvMode = gSrv.arg("ovmode").toInt() ? 1 : 0;
  if (gSrv.hasArg("ox"))     RemoteFace::gOvX    = (int8_t)gSrv.arg("ox").toInt();
  if (gSrv.hasArg("oy"))     RemoteFace::gOvY    = (int8_t)gSrv.arg("oy").toInt();
  if (gSrv.hasArg("ox2"))    RemoteFace::gOvX2   = (int8_t)gSrv.arg("ox2").toInt();
  if (gSrv.hasArg("ovs"))    RemoteFace::gOvScale= (uint8_t)gSrv.arg("ovs").toInt();
  if (gSrv.hasArg("ovfg"))   RemoteFace::gOvFG   = (uint8_t)gSrv.arg("ovfg").toInt();
  if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
  Serial.printf("[HTTP] anim start frames=%d fps=%d overlay=%d burst=%d ovmode=%u ox=%d oy=%d ox2=%d fg=%u\n",
                frames, fps, ov, burst, RemoteFace::gOvMode, RemoteFace::gOvX,
                RemoteFace::gOvY, RemoteFace::gOvX2, RemoteFace::gOvFG);
  gSrv.send(200, "text/plain", "ANIM OK frames=" + String(frames));
}

// 保存当前动画到 flash：POST /animsave（重启自动播放）
void handleAnimSave() {
  if (RemoteFace::saveAnimToFs()) gSrv.send(200, "text/plain", "SAVED");
  else gSrv.send(500, "text/plain", "SAVE FAIL");
}

// 播放 flash 里的动画：POST /animload
void handleAnimLoad() {
  if (RemoteFace::loadAnimFromFs()) {
    if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
    gSrv.send(200, "text/plain", "LOADED");
  } else {
    gSrv.send(404, "text/plain", "NO ANIM");
  }
}

// 动画状态：GET /animlist → JSON
void handleAnimList() {
  String j = "{\"frames\":" + String((int)RemoteFace::gAnimFrames) +
             ",\"fps\":"    + String((int)RemoteFace::gAnimFps) +
             ",\"overlay\":" + String(RemoteFace::gAnimOverlay ? 1 : 0) +
             ",\"burst\":"  + String(RemoteFace::gAnimBurst ? 1 : 0) +
             ",\"cap\":"    + String((int)RemoteFace::gAnimCap) +
             ",\"fs\":"     + String(RemoteFace::hasAnimFs() ? 1 : 0) +
             ",\"ovmode\":" + String((int)RemoteFace::gOvMode) +
             ",\"ovx\":"    + String((int)RemoteFace::gOvX) +
             ",\"ovy\":"    + String((int)RemoteFace::gOvY) +
             ",\"ovx2\":"   + String((int)RemoteFace::gOvX2) +
             ",\"ovs\":"    + String((int)RemoteFace::gOvScale) +
             ",\"ovfg\":"   + String((int)RemoteFace::gOvFG) + "}";
  gSrv.send(200, "application/json", j);
}

void startPortal() {
  gMode = MODE_PORTAL;
  WiFi.persistent(false);
  WiFi.mode(WIFI_AP);
  // v0.3.14：BLE 开启时 esp_wifi_start 同样要求 modem-sleep 不能禁用，
  // 门户(AP)模式亦不例外；设 MIN_MODEM 通过共存校验（AP 实际不睡，无副作用）。
#if ENABLE_BLE
  esp_wifi_set_ps(WIFI_PS_MIN_MODEM);
#endif
  // 开放网络，无密码，方便手机直连
  WiFi.softAP(gApName);
  gIp = WiFi.softAPIP();

  gDns.setErrorReplyCode(DNSReplyCode::NoError);
  gDns.start(53, "*", gIp);

  gSrv.on("/", HTTP_GET, handleRoot);
  gSrv.on("/save", HTTP_POST, handleSave);
  gSrv.on("/setname", HTTP_POST, handleSetName);   // 多板部署：网页设独立主机名
  gSrv.onNotFound(handleNotFound);
  // softAP 协议栈已创建，此处 begin() 安全（skill 红线顺序）
  gSrv.begin();
  gServerUp = true;

  Serial.printf("[NET] portal AP: %s  http://%s/\n", gApName, gIp.toString().c_str());
  if (gShowIp) gShowIp(gIp.toString().c_str(), true);
}

void startSta() {
  gMode = MODE_STA;
  String ssid, pass;
  loadCreds(ssid, pass);
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  // v0.3.13：关 modem-sleep！默认开 sleep 时 ESP32 周期性关射频保活 association，
  // 路由器（tt112233）实锤周期性 AUTH_EXPIRE 踢站——网页传一半（~5.7KB=snd_buf）
  // TCP 就被掐断，用户看到"网页打不开/一直重新连"。关 sleep 后射频常醒。
  // v0.3.14：但 BLE 开启时 ESP-IDF 在 esp_wifi_start 硬性要求 modem-sleep 不能禁用
  // （否则直接 abort："Should enable WiFi modem sleep when both WiFi and Bluetooth
  // are enabled"）。因此 BLE 开启时改用 MIN_MODEM（轻度休眠，仅 DTIM 间隔唤醒），
  // 既通过共存校验、又比默认 MAX_MODEM 维持关联更稳，最大限度规避路由器踢站。
#if ENABLE_BLE
  esp_wifi_set_ps(WIFI_PS_MIN_MODEM);   // 轻度休眠：共存强制要求 + 维持关联
#else
  WiFi.setSleep(false);                 // 纯 WiFi：射频常醒，根除 AUTH_EXPIRE 掐 TCP
#endif
  WiFi.setHostname(gHostname.c_str());   // 多板部署：DHCP 主机名 = 自定义名
  WiFi.setAutoReconnect(true);           // AUTH_EXPIRE 后协议栈自动重连（不靠 watchdog）
  WiFi.begin(ssid.c_str(), pass.c_str());
  gStaDeadline = millis() + STA_TIMEOUT;
  Serial.printf("[NET] connecting to %s ...\n", ssid.c_str());

  // STA 模式也起一个轻量 HTTP 服务：网页推送器 + PC/浏览器 POST /pushface 推表盘
  gSrv.on("/", HTTP_GET, handleHome);
  gSrv.on("/pushface", HTTP_POST, handlePushFace);
  gSrv.on("/face", HTTP_POST, handleFace);
  gSrv.on("/anim", HTTP_POST, handleAnim);
  gSrv.on("/animsave", HTTP_POST, handleAnimSave);
  gSrv.on("/animload", HTTP_POST, handleAnimLoad);
  gSrv.on("/animlist", HTTP_GET, handleAnimList);
  gSrv.on("/dialup", HTTP_POST, handleDialUp);
  gSrv.on("/diallist", HTTP_GET, handleDialList);
  gSrv.on("/dialpreview", HTTP_GET, handleDialPreview);
  gSrv.on("/dialplay", HTTP_POST, handleDialPlay);
  gSrv.on("/dialov", HTTP_POST, handleDialOv);
  gSrv.on("/dialdel", HTTP_POST, handleDialDel);
  gSrv.on("/status", HTTP_GET, handleStatus);
  gSrv.on("/faces", HTTP_GET, handleFaces);   // v0.3.15：表盘商店预览（按需 gzip 下发）
  gSrv.on("/brightness", HTTP_GET, handleBrightnessGet);
  gSrv.on("/brightness", HTTP_POST, handleBrightnessSet);
  gSrv.on("/rotate", HTTP_GET, handleRotate);      // v0.3.22：屏幕旋转（GET=循环切换）
  gSrv.on("/rotate", HTTP_POST, handleRotate);     // v0.3.22：POST ?v=0..3 指定角度（网页按钮用）
  gSrv.on("/wifi", HTTP_GET, handleWifiGet);       // v0.3.23：WiFi 切换（GET=当前 SSID）
  gSrv.on("/wifi", HTTP_POST, handleWifiSet);      // v0.3.23：POST 换 WiFi → 保存重启
  gSrv.on("/setname", HTTP_POST, handleSetName);   // 多板部署：网页设独立主机名
  gSrv.onNotFound(handleNotFound);
  gSrv.begin();
  gServerUp = true;
  Serial.printf("[NET] http server: / (web pusher) + POST /pushface + /anim\n");
}

void handleStatus() {
  String j = "{\"ip\":\"" + gIp.toString() + "\",\"rssi\":" + String(WiFi.RSSI()) +
             ",\"host\":\"" + gHostname + "\"" +
             ",\"push\":" + String((int)RemoteFace::gStatus) +
             ",\"bright\":" + String((int)Display::brightness()) +
             ",\"rot\":" + String((int)gRot) + "}";
  gSrv.send(200, "application/json", j);
}

// ---------- 屏幕亮度 ----------
//   GET  /brightness      → {"level":N}（N=0~255，当前目标亮度）
//   POST /brightness?level=N  → 设置并持久化（N 越界自动夹到 0~255）
//   夜间息屏时段会临时压到 dimLevel，设置的是「日间目标亮度」。
void handleBrightnessGet() {
  String j = "{\"level\":" + String((int)Display::brightness()) + "}";
  gSrv.send(200, "application/json", j);
}

void handleBrightnessSet() {
  if (!gSrv.hasArg("level")) { gSrv.send(400, "text/plain", "need level"); return; }
  int v = gSrv.arg("level").toInt();
  if (v < 0) v = 0;
  if (v > 255) v = 255;
  Display::setBrightness((uint8_t)v);
  String j = "{\"level\":" + String(v) + "}";
  gSrv.send(200, "application/json", j);
  Serial.printf("[NET] brightness set to %d\n", v);
}

// ---------- 屏幕旋转（v0.3.22）----------
// GET  /rotate        → 循环切换 0°→90°→180°→270°→0°（手机一键翻转最方便）
// POST /rotate?v=0..3 → 直接指定角度；两种都写 NVS 持久化，重启保持
void handleRotate() {
  int v;
  if (gSrv.hasArg("v")) {
    v = gSrv.arg("v").toInt();
    if (v < 0 || v > 3) { gSrv.send(400, "text/plain", "need v=0..3"); return; }
  } else {
    v = (gRot + 1) & 3;
  }
  gRot = (uint8_t)v;
  gPrefs.begin("netcfg", false);
  gPrefs.putUChar("rot", gRot);
  gPrefs.end();
  String j = "{\"rot\":" + String(v) + ",\"deg\":" + String(v * 90) + "}";
  gSrv.send(200, "application/json", j);
  Serial.printf("[NET] rotation -> %d (%d deg)\n", v, v * 90);
}

// ---------- WiFi 切换（v0.3.23）----------
// GET  /wifi              → {"ssid":"xx"} 当前连接的 SSID（不回显密码）
// POST /wifi?ssid=&pass=  → 保存新凭据并重启。
//   安全性：若新 WiFi 连不上，开机流程「STA timeout -> portal」会自动退回
//   配网热点（PixelClock-Setup），板子不会失联，无需重刷。
void handleWifiGet() {
  String j = "{\"ssid\":\"" + WiFi.SSID() + "\"}";
  gSrv.send(200, "application/json", j);
}

void handleWifiSet() {
  if (!gSrv.hasArg("ssid")) { gSrv.send(400, "text/plain", "need ssid"); return; }
  String ssid = gSrv.arg("ssid");
  String pass = gSrv.hasArg("pass") ? gSrv.arg("pass") : String("");
  ssid.trim();
  if (ssid.length() == 0 || ssid.length() > 32) {
    gSrv.send(400, "text/plain", "bad ssid"); return;
  }
  if (pass.length() > 0 && pass.length() < 8) {
    gSrv.send(400, "text/plain", "pass too short"); return;
  }
  saveCreds(ssid, pass);
  Serial.printf("[NET] wifi switch -> \"%s\", rebooting...\n", ssid.c_str());
  gSrv.send(200, "application/json", "{\"ok\":1,\"ssid\":\"" + ssid +
             "\",\"msg\":\"rebooting\"}");
  delay(500);                       // 等响应包发完再重启
  ESP.restart();
}

// ---------- FS 表盘库（LittleFS /dials/，数量不受固件体积限制） ----------
//  POST /dialup?name=<stem>&off=N&len=M&fps=F&overlay=0|1&burst=0|1&final=1[&play=1]
//       body=HEX 分块（1024B/块）；off=0 截断新建；final=1 写 meta 收尾
//       叠加层参数（可选）：ovmode=0|1&ox=&oy=&ox2=&ovs=&ovfg=  （经典/方块 + 位置 + 前景色）
//  POST /dialov?name=<stem>&mode=&ox=&oy=&ox2=&ovs=&ovfg=[&ov=]  实时调整已存表盘的叠加层
//  GET  /diallist                  → {"dials":[{"n","c","f","o","b","s","m","x","y","x2","sc"}...]}
//  GET  /dialpreview?name=<stem>   → 首帧 8192B 的 base64（页面画缩略图）
//  POST /dialplay?name=<stem>      → 从 FS 载入表盘并立即播放

static File     gDialFile;
static String   gDialName;
static uint32_t gDialBytes = 0;
static String   gCurDial;                 // 当前从 FS 播放的表盘 stem（/dialov 热更新用）
static const uint16_t CHUNK_MAX = 4096;   // 单分片二进制上限（hex 翻倍）

// 表盘 meta：/dials/<stem>.json，一行 "%d %d %d %d %d %d %d %d %d"
// = fps overlay burst mode ox oy ox2 scale fg（0.3.x 前只有前 3 项，缺省补齐）
struct DialMeta {
  int fps = 6, ov = 1, bu = 0;
  int mode = 0, ox = -1, oy = 46, ox2 = 34, scale = 2, fg = 0;
};

static void clampOv(DialMeta& m) {
  if (m.mode != 0) m.mode = 1;
  if (m.mode == 0) {
    if (m.ox < -1) m.ox = -1;
    if (m.ox > 64) m.ox = 64;
    if (m.oy < 0)  m.oy = 0;
    if (m.oy > 50) m.oy = 50;             // 字高 7*scale，最大字号 2 → 14 行
  } else {
    if (m.ox < 0)  m.ox = 0;
    if (m.ox > 45) m.ox = 45;             // 块宽 19
    if (m.ox2 < 0)  m.ox2 = 0;
    if (m.ox2 > 45) m.ox2 = 45;
    if (m.oy < 0)  m.oy = 0;
    if (m.oy > 45) m.oy = 45;             // 块高 19
  }
  if (m.scale < 1) m.scale = 1;
  if (m.scale > 2) m.scale = 2;             // "HH:MM" 宽 6*scale-1/字符，scale3=87px 超 64 面板
  if (m.fg < 0 || m.fg > 2) m.fg = 0;        // 0=白 1=黑 2=黄
}

static bool readDialMeta(const String& stem, DialMeta& m) {
  File mf = LittleFS.open("/dials/" + stem + ".json", "r");
  if (!mf) return false;
  String line = mf.readStringUntil('\n');
  mf.close();
  line.trim();
  int fps = 6, ov = 1, bu = 0, mode = 0, ox = -1, oy = 46, ox2 = 34, scale = 2, fg = 0;
  int nf = sscanf(line.c_str(), "%d %d %d %d %d %d %d %d %d",
                  &fps, &ov, &bu, &mode, &ox, &oy, &ox2, &scale, &fg);
  if (nf < 1) return false;
  m.fps = fps; m.ov = ov; m.bu = bu;
  m.mode = (nf >= 4) ? mode : 0;
  m.ox   = (nf >= 5) ? ox   : -1;
  m.oy   = (nf >= 6) ? oy   : 46;
  m.ox2  = (nf >= 7) ? ox2  : 34;
  m.scale= (nf >= 8) ? scale: 2;
  m.fg   = (nf >= 9) ? fg   : 0;
  if (m.mode == 1 && nf < 5) m.ox = 12;   // 旧文件无位置字段：方块模式回退默认块位
  if (m.mode == 1 && nf < 6) m.oy = 11;
  clampOv(m);
  return true;
}

static void writeDialMeta(const String& stem, const DialMeta& m) {
  File mf = LittleFS.open("/dials/" + stem + ".json", "w");
  if (mf) {
    mf.printf("%d %d %d %d %d %d %d %d %d",
              m.fps, m.ov, m.bu, m.mode, m.ox, m.oy, m.ox2, m.scale, m.fg);
    mf.close();
  }
}

// 把 meta 的叠加参数应用到 RemoteFace 全局态
static void applyOv(const DialMeta& m) {
  RemoteFace::gOvMode  = (uint8_t)m.mode;
  RemoteFace::gOvX     = (int8_t)m.ox;
  RemoteFace::gOvY     = (int8_t)m.oy;
  RemoteFace::gOvX2    = (int8_t)m.ox2;
  RemoteFace::gOvScale = (uint8_t)m.scale;
  RemoteFace::gOvFG    = (uint8_t)m.fg;
}

// 从 FS 载入表盘并播放；成功回 true
static bool playDialFromFs(const String& name) {
  if (!RemoteFace::gAnimBuf && !RemoteFace::initAnimBuf()) return false;
  File f = LittleFS.open("/dials/" + name + ".rgb565", "r");
  if (!f) return false;
  size_t sz = f.size();
  if (sz == 0 || sz % RemoteFace::FRAME_BYTES != 0 ||
      sz > (size_t)RemoteFace::gAnimCap * RemoteFace::FRAME_BYTES) {
    f.close();
    return false;
  }
  uint8_t frames = (uint8_t)(sz / RemoteFace::FRAME_BYTES);
  size_t n = f.read(RemoteFace::gAnimBuf, sz);
  f.close();
  if (n != sz) return false;

  DialMeta m;                                 // 无 meta 文件时用默认（fps6/叠加开/经典模式）
  readDialMeta(name, m);
  if (m.fps < 1) m.fps = 1;
  if (m.fps > 30) m.fps = 30;
  memcpy(RemoteFace::gBuf, RemoteFace::gAnimBuf, RemoteFace::FRAME_BYTES);
  RemoteFace::beginAnim(frames, (uint8_t)m.fps, m.ov != 0, m.bu != 0);
  applyOv(m);
  gCurDial = name;
  // v0.3.12：选中即持久化——写 /anim.bin，重启后自动继续播这个表盘
  // （此前只加载到内存，重启后弹回旧动画，用户以为"表盘丢了"）
  RemoteFace::saveAnimToFs();
  Serial.printf("[DIAL] play %s: %u frames fps=%d ov=%d burst=%d ovmode=%d ox=%d oy=%d ox2=%d sc=%d\n",
                name.c_str(), frames, m.fps, m.ov, m.bu, m.mode, m.ox, m.oy, m.ox2, m.scale);
  return true;
}

void handleDialUp() {
  if (!gSrv.hasArg("name")) { gSrv.send(400, "text/plain", "need name"); return; }
  String name = gSrv.arg("name");
  if (name.length() == 0 || name.indexOf('/') >= 0 || name.indexOf("..") >= 0 ||
      name.indexOf('\\') >= 0) {
    gSrv.send(400, "text/plain", "bad name"); return;
  }
  String body = gSrv.arg("plain");
  if (body.length() % 2 != 0) { gSrv.send(400, "text/plain", "bad hex len"); return; }
  uint16_t nbytes = (uint16_t)(body.length() / 2);
  if (nbytes > CHUNK_MAX) { gSrv.send(400, "text/plain", "chunk too big"); return; }
  uint32_t off   = gSrv.hasArg("off") ? (uint32_t)gSrv.arg("off").toInt() : 0;

  if (!LittleFS.exists("/dials")) LittleFS.mkdir("/dials");
  if (off == 0 || !gDialFile || gDialName != name) {
    if (gDialFile) gDialFile.close();
    gDialName  = name;
    gDialBytes = 0;
    gDialFile  = LittleFS.open("/dials/" + name + ".rgb565", "w");
    if (!gDialFile) { gSrv.send(500, "text/plain", "FS OPEN FAIL"); return; }
  }
  if (off != gDialBytes) { gSrv.send(400, "text/plain", "OFF GAP"); return; }
  if (gDialBytes + nbytes > 600000) { gSrv.send(400, "text/plain", "too big"); return; }

  static uint8_t bin[CHUNK_MAX];   // static：loop 任务栈仅 8KB，不能放大缓冲
  for (uint16_t i = 0; i < nbytes; ++i) {
    bin[i] = (uint8_t)((hexVal(body[i * 2]) << 4) | hexVal(body[i * 2 + 1]));
  }
  gDialFile.write(bin, nbytes);
  gDialBytes += nbytes;

  if (gSrv.hasArg("final")) {
    gDialFile.close();
    DialMeta m;
    m.fps  = gSrv.hasArg("fps")     ? gSrv.arg("fps").toInt()     : 6;
    m.ov   = gSrv.hasArg("overlay") ? gSrv.arg("overlay").toInt() : 1;
    m.bu   = gSrv.hasArg("burst")   ? gSrv.arg("burst").toInt()   : 0;
    m.mode = gSrv.hasArg("ovmode")  ? gSrv.arg("ovmode").toInt()  : 0;
    m.ox   = gSrv.hasArg("ox")      ? gSrv.arg("ox").toInt()      : -1;
    m.oy   = gSrv.hasArg("oy")      ? gSrv.arg("oy").toInt()      : 46;
    m.ox2  = gSrv.hasArg("ox2")     ? gSrv.arg("ox2").toInt()     : 34;
    m.scale= gSrv.hasArg("ovs")     ? gSrv.arg("ovs").toInt()     : 2;
    m.fg   = gSrv.hasArg("ovfg")    ? gSrv.arg("ovfg").toInt()    : 0;
    if (m.mode == 1 && !gSrv.hasArg("ox"))  m.ox  = 12;   // 方块模式默认块位
    if (m.mode == 1 && !gSrv.hasArg("oy"))  m.oy  = 11;
    clampOv(m);
    writeDialMeta(name, m);
    Serial.printf("[DIAL] saved %s: %u bytes fps=%d ov=%d burst=%d ovmode=%d ox=%d oy=%d ox2=%d sc=%d fg=%d\n",
                  name.c_str(), gDialBytes, m.fps, m.ov, m.bu, m.mode, m.ox, m.oy, m.ox2, m.scale, m.fg);
    if (gSrv.hasArg("play") && gFaceSel) gFaceSel(FACE_IDX_REMOTE);
    if (gSrv.hasArg("play")) playDialFromFs(name);
    gSrv.send(200, "text/plain", "DIAL SAVED " + name);
    return;
  }
  gSrv.send(200, "text/plain", "CHUNK " + String(off) + "+" + String(nbytes));
}

// 实时调整已存表盘的叠加层：POST /dialov?name=x&mode=0|1&ox=&oy=&ox2=&ovs=&ovfg=[&ov=]
// 只传要改的字段；若该表盘正在播放立即生效，meta 同步落盘
void handleDialOv() {
  if (!gSrv.hasArg("name")) { gSrv.send(400, "text/plain", "need name"); return; }
  String name = gSrv.arg("name");
  if (name.length() == 0 || name.indexOf('/') >= 0 || name.indexOf("..") >= 0 ||
      name.indexOf('\\') >= 0) {
    gSrv.send(400, "text/plain", "bad name"); return;
  }
  DialMeta m;
  if (!readDialMeta(name, m)) {
    // meta 不存在（极旧表盘）：按 overlay 开 + 经典默认起步
    m = DialMeta();
  }
  if (gSrv.hasArg("mode"))  m.mode  = gSrv.arg("mode").toInt()  ? 1 : 0;
  if (gSrv.hasArg("ox"))    m.ox    = gSrv.arg("ox").toInt();
  if (gSrv.hasArg("oy"))    m.oy    = gSrv.arg("oy").toInt();
  if (gSrv.hasArg("ox2"))   m.ox2   = gSrv.arg("ox2").toInt();
  if (gSrv.hasArg("ovs"))   m.scale = gSrv.arg("ovs").toInt();
  if (gSrv.hasArg("ovfg"))  m.fg    = gSrv.arg("ovfg").toInt();
  if (gSrv.hasArg("ov")) {
    m.ov = gSrv.arg("ov").toInt() ? 1 : 0;
    if (m.ov && gCurDial == name) RemoteFace::gAnimOverlay = true;
    if (!m.ov && gCurDial == name) RemoteFace::gAnimOverlay = false;
  }
  clampOv(m);
  writeDialMeta(name, m);
  if (gCurDial == name) applyOv(m);          // 正在播放 → 下一帧立即生效
  Serial.printf("[DIAL] ov %s: mode=%d ox=%d oy=%d ox2=%d sc=%d fg=%d ov=%d%s\n",
                name.c_str(), m.mode, m.ox, m.oy, m.ox2, m.scale, m.fg, m.ov,
                (gCurDial == name) ? " (live)" : "");
  gSrv.send(200, "text/plain", "OV OK " + name);
}

void handleDialList() {
  String j = "{\"dials\":[";
  bool first = true;
  if (LittleFS.exists("/dials")) {
    File dir = LittleFS.open("/dials", "r");
    if (dir && dir.isDirectory()) {
      File f = dir.openNextFile();
      while (f) {
        String fn = f.name();
        size_t sz = f.size();
        f = dir.openNextFile();          // 先步进再处理（旧 File 析构关闭）
        if (!fn.endsWith(".rgb565") || sz == 0) continue;
        String stem = fn;
        int slash = stem.lastIndexOf('/');
        if (slash >= 0) stem = stem.substring(slash + 1);
        stem.replace(".rgb565", "");
        DialMeta m;
        readDialMeta(stem, m);
        if (!first) j += ",";
        first = false;
        j += "{\"n\":\"" + stem + "\",\"c\":" + String((int)(sz / 8192)) +
             ",\"f\":" + String(m.fps) + ",\"o\":" + String(m.ov) +
             ",\"b\":" + String(m.bu) + ",\"s\":" + String((unsigned)sz) +
             ",\"m\":" + String(m.mode) + ",\"x\":" + String(m.ox) +
             ",\"y\":" + String(m.oy) + ",\"x2\":" + String(m.ox2) +
             ",\"sc\":" + String(m.scale) + ",\"fg\":" + String(m.fg) + "}";
      }
    }
  }
  j += "]}";
  gSrv.send(200, "application/json", j);
}

void handleDialPreview() {
  if (!gSrv.hasArg("name")) { gSrv.send(400, "text/plain", "need name"); return; }
  String name = gSrv.arg("name");
  File f = LittleFS.open("/dials/" + name + ".rgb565", "r");
  if (!f) { gSrv.send(404, "text/plain", "no dial"); return; }
  static uint8_t buf[8192];   // 必须 static：loop 任务栈只有 8KB，栈上放 8KB 缓冲必崩
  size_t n = f.read(buf, sizeof(buf));
  f.close();
  static const char* B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  String out;
  out.reserve((n + 2) / 3 * 4 + 4);
  for (size_t i = 0; i < n; i += 3) {
    uint32_t v = (uint32_t)buf[i] << 16;
    if (i + 1 < n) v |= (uint32_t)buf[i + 1] << 8;
    if (i + 2 < n) v |= (uint32_t)buf[i + 2];
    out += B64[(v >> 18) & 0x3F];
    out += B64[(v >> 12) & 0x3F];
    out += (i + 1 < n) ? B64[(v >> 6) & 0x3F] : '=';
    out += (i + 2 < n) ? B64[v & 0x3F] : '=';
  }
  gSrv.send(200, "text/plain", out);
}

void handleDialPlay() {
  if (!gSrv.hasArg("name")) { gSrv.send(400, "text/plain", "need name"); return; }
  String name = gSrv.arg("name");
  if (name.indexOf('/') >= 0 || name.indexOf("..") >= 0) {
    gSrv.send(400, "text/plain", "bad name"); return;
  }
  if (!playDialFromFs(name)) { gSrv.send(404, "text/plain", "LOAD FAIL"); return; }
  if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
  gSrv.send(200, "text/plain", "PLAY " + name);
}

// 删除 FS 表盘：POST /dialdel?name=<stem>
//   删 /dials/<stem>.rgb565 与 .json（meta）；若该表盘正在播放则切回时钟，避免空帧。
//   仅删文件，不动其它表盘，不动文件系统结构。
void handleDialDel() {
  if (!gSrv.hasArg("name")) { gSrv.send(400, "text/plain", "need name"); return; }
  String name = gSrv.arg("name");
  if (name.length() == 0 || name.indexOf('/') >= 0 || name.indexOf("..") >= 0 ||
      name.indexOf('\\') >= 0) {
    gSrv.send(400, "text/plain", "bad name"); return;
  }
  String f1 = "/dials/" + name + ".rgb565";
  String f2 = "/dials/" + name + ".json";
  bool had = false;
  if (LittleFS.exists(f1)) { LittleFS.remove(f1); had = true; }
  if (LittleFS.exists(f2)) { LittleFS.remove(f2); had = true; }
  if (!had) { gSrv.send(404, "text/plain", "NO SUCH DIAL"); return; }
  // 正在播放的就是被删的表盘 → 切回默认时钟，防止空帧黑屏
  if (gCurDial == name) {
    gCurDial = "";
    Serial.println("[DIAL] deleted playing dial -> fall back to CLOCK");
    if (gFaceSel) gFaceSel(FACE_IDX_CLOCK);
  }
  Serial.printf("[DIAL] deleted %s (rgb565+json)\n", name.c_str());
  gSrv.send(200, "text/plain", "DELETED " + name);
}

}  // namespace

// ============================================================
// BLE 通道播放表盘（v0.3.14）：与 HTTP /dialplay 同一实现，
// 播放成功后切 REMOTE 面；playDialFromFs 内部已做持久化（重启续播）。
bool playDial(const char* name) {
  if (!name || !*name) return false;
  String n(name);
  n.trim();
  if (n.length() == 0 || n.indexOf('/') >= 0 || n.indexOf("..") >= 0) return false;
  if (!playDialFromFs(n)) return false;
  if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
  return true;
}

// ============================================================
void begin(const char* apName, ShowIpFn showIp) {
  gShowIp = showIp;
  gApName = apName;
  loadHostname();                 // 多板部署：先读 /hostname.txt（默认 pixelclock）

  String ssid, pass;
  if (!loadCreds(ssid, pass)) {
    Serial.println("[NET] no creds -> portal");
    startPortal();
    return;
  }
  startSta();
}

void loop() {
  // HTTP 服务（STA 与 PORTAL 两种模式都起服务）
  if (gServerUp) gSrv.handleClient();

  switch (gMode) {
    case MODE_STA: {
      if (WiFi.status() == WL_CONNECTED) {
        gIp = WiFi.localIP();
        Serial.printf("[NET] up, ip=%s rssi=%d\n",
                      gIp.toString().c_str(), WiFi.RSSI());
        if (gShowIp) gShowIp(gIp.toString().c_str(), false);
        gMode = MODE_IDLE;
        return;
      }
      if (millis() > gStaDeadline) {
        Serial.println("[NET] STA timeout -> portal");
        startPortal();
      }
      break;
    }
    case MODE_PORTAL:
      gDns.processNextRequest();
      break;
    case MODE_IDLE:
    default: {
      // ---- v0.3.16：HTTP 服务自检（TCP 假死检测，见上方注释）----
      httpSelfCheck();
      // ---- WiFi 看门狗（MODE_IDLE = STA 已连过，之后只管盯着）----
      if (WiFi.status() == WL_CONNECTED) {
        gIp = WiFi.localIP();
        gDownSince = 0;
        if (!gMdnsUp) {          // 连上后注册一次 mDNS：http://<hostname>.local/
          if (MDNS.begin(gHostname.c_str())) {
            MDNS.addService("http", "tcp", 80);
            gMdnsUp = true;
            Serial.printf("[NET] mDNS up: http://%s.local/\n", gHostname.c_str());
          }
        }
      } else {
        if (gDownSince == 0) {
          gDownSince = millis();
          gMdnsUp = false;
          Serial.println("[NET] WiFi lost, watchdog armed (8s)");
        } else if (millis() - gDownSince > 8000) {
          gDownSince = millis();
          Serial.println("[NET] watchdog: reconnecting WiFi...");
          WiFi.disconnect();
          WiFi.reconnect();
        }
      }
      break;
    }
  }
}

bool staConnected() { return WiFi.status() == WL_CONNECTED; }

void setFaceSelect(FaceSelectFn fn) { gFaceSel = fn; }

void reset() {
  gPrefs.begin("netcfg", false);
  gPrefs.clear();
  gPrefs.end();
  Serial.println("[NET] creds cleared, rebooting");
  delay(300);
  ESP.restart();
}

}  // namespace Net

#endif  // ARDUINO
