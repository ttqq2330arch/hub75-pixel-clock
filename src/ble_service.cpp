// ============================================================
//  ble_service.cpp — BLE 服务（Arduino core 2.0.x BLEDevice 经典 API）
// ------------------------------------------------------------
//  注意：ESPRESSIF32 6.5.0 锁死在 core 2.0.17 —— core 3.x 把
//  BLE 头文件路径/API 全改了（NimBLE 化），别手贱升 platform。
//  BLE + HUB75 DMA 在 S3 上 RAM 实测可共存（BLE 约 50KB，
//  64x64 双缓冲位平面 40-70KB，S3 SRAM 512KB 余量充足）。
//
//  特征一览（v0.3.14 起）：
//    TIME   …0002 write       uint32 LE 秒      设置时间
//    TIME_R …0003 read        uint32 LE 秒      读时间
//    FACE   …0004 write       uint8             切换表盘索引
//    DATA   …0005 write(+NR)  帧协议             推送表盘（M3）
//    STATUS …0006 read+notify uint8             推送状态码
//    BRIGHT …0007 write       uint8 0~255       亮度（v0.3.14）
//    DIAL   …0008 write       string            播放 FS 表盘 stem（v0.3.14）
//  协议细节：docs/face-push-protocol.md
// ============================================================
#include "ble_service.h"
#include "config.h"
#include "clock_time.h"
#include "faces_access.h"
#include "face_remote.h"
#include "display_mgr.h"
#include "net.h"

#ifdef ARDUINO
#if ENABLE_BLE   // 0.3.0 起默认关蓝牙（纯 WiFi），整块不编译省 ~50KB 堆

#include <Arduino.h>
#include <string>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

namespace Ble {

namespace {

// 连接状态跟踪 + 闲置看门狗计时（供 SrvCb 与各特征回调刷新）
BLEServer*        gSrv      = nullptr;  // 服务指针（看门狗踢连接用）
bool              gConnUp   = false;    // 当前是否有客户端连着
uint32_t          gLastActivityMs = 0;  // 最近一次读写活动（看门狗计时）

// 闲置踢连接：微信小程序退后台/被杀后往往不释放 GATT 连接，
// 设备会卡在"已连接→不广播"状态，手机再扫就什么都扫不到。
// 90s 无任何读写活动 → 主动断开，onDisconnect 会负责重新广播。
const uint32_t    IDLE_KICK_MS = 90000;

// 断线后自动重新广播，方便小程序反复重连（否则只广播一次，连过就搜不到）
class SrvCb : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) override {
    gConnUp = true;
    gLastActivityMs = millis();
    Serial.println("[BLE] client connected");
  }
  void onDisconnect(BLEServer* pServer) override {
    gConnUp = false;
    BLEDevice::getAdvertising()->start();
    Serial.println("[BLE] client disconnected, re-advertising");
  }
};


const char* SVC_UUID  = "4f8c0000-1f0a-4c1e-9b2d-000000000001";
const char* CH_TIME   = "4f8c0000-1f0a-4c1e-9b2d-000000000002";  // write  设置时间
const char* CH_TIME_R = "4f8c0000-1f0a-4c1e-9b2d-000000000003";  // read   读时间
const char* CH_FACE   = "4f8c0000-1f0a-4c1e-9b2d-000000000004";  // write  切换表盘
const char* CH_DATA   = "4f8c0000-1f0a-4c1e-9b2d-000000000005";  // write  表盘数据流
const char* CH_STATUS = "4f8c0000-1f0a-4c1e-9b2d-000000000006";  // read+notify 推送状态
const char* CH_BRIGHT = "4f8c0000-1f0a-4c1e-9b2d-000000000007";  // write  uint8 亮度 0~255（v0.3.14）
const char* CH_DIAL   = "4f8c0000-1f0a-4c1e-9b2d-000000000008";  // write  string FS 表盘 stem（v0.3.14）

// 帧协议命令字（DATA 特征首字节）
enum : uint8_t {
  CMD_DATA   = 0x01,  // [01][off_lo][off_hi][len][payload...]
  CMD_COMMIT = 0x02,  // [02][crc_lo][crc_hi]
  CMD_ABORT  = 0x03,  // [03]
};

FaceSelectFn      gFaceSel   = nullptr;
BLECharacteristic* gChTimeR  = nullptr;
BLECharacteristic* gChStatus = nullptr;
uint8_t           gLastStatus = 0xFF;   // 上次通知出去的状态（0xFF=从未）

// ---- TIME: uint32 LE 秒 ----
class TimeCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    gLastActivityMs = millis();
    std::string v = c->getValue();
    if (v.length() < 4) return;
    uint32_t e = (uint8_t)v[0] | ((uint8_t)v[1] << 8)
               | ((uint8_t)v[2] << 16) | ((uint8_t)v[3] << 24);
    ClockT::setEpoch(e);
  }
  void onRead(BLECharacteristic* c) override { gLastActivityMs = millis(); }
};

// ---- FACE: uint8 表盘索引 ----
class FaceCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    gLastActivityMs = millis();
    std::string v = c->getValue();
    if (v.length() < 1 || !gFaceSel) return;
    gFaceSel((uint8_t)v[0]);
  }
};

// ---- DATA: 表盘帧协议 ----
class DataCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    gLastActivityMs = millis();
    std::string v = c->getValue();
    if (v.empty()) return;
    const uint8_t* p = (const uint8_t*)v.data();
    size_t n = v.length();

    switch (p[0]) {
      case CMD_DATA: {
        if (n < 4) return;
        uint16_t off = (uint16_t)(p[1] | (p[2] << 8));
        uint16_t len = p[3];
        if (n < (size_t)(4 + len)) return;          // 长度字段与实收不符
        if (off == 0) RemoteFace::beginRx();        // 偏移 0 = 新帧开始
        if (!RemoteFace::writeChunk(off, p + 4, len)) {
          RemoteFace::abortRx();                    // 越界/状态错 → 放弃
          Serial.println("[BLE] data chunk rejected");
        }
        break;
      }
      case CMD_COMMIT: {
        if (n < 3) return;
        uint16_t crc = (uint16_t)(p[1] | (p[2] << 8));
        if (RemoteFace::commit(crc)) {
          Serial.println("[BLE] face committed, switching to REMOTE");
          if (gFaceSel) gFaceSel(FACE_IDX_REMOTE);
        } else {
          Serial.println("[BLE] face CRC fail");
        }
        break;
      }
      case CMD_ABORT:
        RemoteFace::abortRx();
        break;
      default:
        break;
    }
  }
};

// ---- STATUS: read + notify（客户端轮询读取也算"活着"）----
class StatusCb : public BLECharacteristicCallbacks {
  void onRead(BLECharacteristic* c) override { gLastActivityMs = millis(); }
};

// ---- BRIGHT: uint8 亮度 0~255（v0.3.14，体验版小程序无域名通道）----
class BrightCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    gLastActivityMs = millis();
    std::string v = c->getValue();
    if (v.empty()) return;
    Display::setBrightness((uint8_t)v[0]);
    Serial.printf("[BLE] brightness -> %u\n", (unsigned)(uint8_t)v[0]);
  }
};

// ---- DIAL: string 播放 FS 表盘 stem（v0.3.14）----
// 体验版小程序无法读 /diallist（域名限制），列表走本地缓存，
// 这里只负责"按名字播放"。Net::playDial 与 HTTP /dialplay 同实现。
class DialCb : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    gLastActivityMs = millis();
    std::string v = c->getValue();
    if (v.empty()) return;
    String name(v.c_str());
    name.trim();
    if (Net::playDial(name.c_str())) {
      Serial.printf("[BLE] play dial %s\n", name.c_str());
    } else {
      Serial.printf("[BLE] dial not found: %s\n", name.c_str());
    }
  }
};

}  // namespace

void begin(FaceSelectFn faceSel) {
  gFaceSel = faceSel;

  BLEDevice::init("PixelClock");
  gSrv = BLEDevice::createServer();
  gSrv->setCallbacks(new SrvCb());
  BLEService* svc = gSrv->createService(SVC_UUID);

  BLECharacteristic* chTime = svc->createCharacteristic(
      CH_TIME, BLECharacteristic::PROPERTY_WRITE);
  chTime->setCallbacks(new TimeCb());

  gChTimeR = svc->createCharacteristic(
      CH_TIME_R, BLECharacteristic::PROPERTY_READ);
  gChTimeR->setValue((uint8_t*)"\0\0\0\0", 4);

  BLECharacteristic* chFace = svc->createCharacteristic(
      CH_FACE, BLECharacteristic::PROPERTY_WRITE);
  chFace->setCallbacks(new FaceCb());

  // 表盘数据流：同时开 write / write-no-response，
  // 客户端可任选（小程序走 write，桌面工具可走 NR 提速）
  BLECharacteristic* chData = svc->createCharacteristic(
      CH_DATA, BLECharacteristic::PROPERTY_WRITE |
                   BLECharacteristic::PROPERTY_WRITE_NR);
  chData->setCallbacks(new DataCb());

  // 推送状态：read + notify（RemoteFace::gStatus 的镜像）
  gChStatus = svc->createCharacteristic(
      CH_STATUS, BLECharacteristic::PROPERTY_READ |
                 BLECharacteristic::PROPERTY_NOTIFY);
  uint8_t st = RemoteFace::gStatus;
  gChStatus->setValue(&st, 1);
  gChStatus->setCallbacks(new StatusCb());
  gLastStatus = 0xFF;

  // v0.3.14：亮度 + FS 表盘播放（体验版小程序蓝牙控制用）
  BLECharacteristic* chBright = svc->createCharacteristic(
      CH_BRIGHT, BLECharacteristic::PROPERTY_WRITE);
  chBright->setCallbacks(new BrightCb());

  BLECharacteristic* chDial = svc->createCharacteristic(
      CH_DIAL, BLECharacteristic::PROPERTY_WRITE);
  chDial->setCallbacks(new DialCb());

  svc->start();
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(SVC_UUID);
  adv->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.println("[BLE] advertising as \"PixelClock\"");
}

void loop() {
  uint32_t now = millis();

  // 1) 接收超时看门狗（传输中断了要把状态推成 ABORT）
  RemoteFace::tickTimeout(now);

  // 2) TIME_READ 特征跟随系统时间刷新（1s 级，客户端轮询）
  static uint32_t lastPush = 0;
  if (gChTimeR && now - lastPush >= 1000) {
    lastPush = now;
    uint32_t e = ClockT::epoch();
    uint8_t buf[4] = { (uint8_t)(e), (uint8_t)(e >> 8),
                       (uint8_t)(e >> 16), (uint8_t)(e >> 24) };
    gChTimeR->setValue(buf, 4);
  }

  // 3) STATUS 特征：状态一变就 notify 推送
  if (gChStatus) {
    uint8_t st = RemoteFace::gStatus;
    if (st != gLastStatus) {
      gChStatus->setValue(&st, 1);
      gChStatus->notify();
      gLastStatus = st;
      Serial.printf("[BLE] push status -> %u\n", st);
    }
  }

  // 4) 闲置看门狗：连着但超过 90s 没有任何读写活动 → 主动踢掉，
  //    让设备恢复广播（否则小程序退后台不释放连接时手机永远扫不到）。
  //    断开动作会触发 SrvCb::onDisconnect 自动重新广播。
  if (gConnUp && gSrv && gSrv->getConnectedCount() > 0 &&
      now - gLastActivityMs > IDLE_KICK_MS) {
    Serial.printf("[BLE] idle %lus, kicking client to re-advertise\n",
                  (unsigned long)((now - gLastActivityMs) / 1000));
    gSrv->disconnect(gSrv->getConnId());
  }
}

}  // namespace Ble

#endif  // ENABLE_BLE
#endif  // ARDUINO
