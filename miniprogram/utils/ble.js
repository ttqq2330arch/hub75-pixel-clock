// utils/ble.js — BLE 管理器，对接 ESP32-S3 固件 src/ble_service.cpp
//
// 服务 UUID: 4f8c0000-1f0a-4c1e-9b2d-000000000001
//   TIME   (…0002, write)       uint32 LE 秒  → 设置时间
//   TIME_R (…0003, read)        uint32 LE 秒  → 读时间
//   FACE   (…0004, write)       uint8         → 切换表盘索引
//   DATA   (…0005, write)       表盘帧协议     → 推送表盘（M3）
//   STATUS (…0006, read+notify) uint8         → 推送状态码
//
// 帧协议（详见 docs/face-push-protocol.md）：
//   0x01 数据块 [01][off_lo][off_hi][len][payload...]
//   0x02 提交   [02][crc_lo][crc_hi]   CRC16-XMODEM 全帧 8192 字节校验
//   0x03 中止   [03]
// 状态码：0 空闲 / 1 接收中 / 2 成功已切换 / 3 CRC 失败 / 4 中止或超时
//
// 设备名: "PixelClock"

const render = require('./render.js')

const SERVICE_UUID = '4f8c0000-1f0a-4c1e-9b2d-000000000001'
const CH = {
  TIME: '4f8c0000-1f0a-4c1e-9b2d-000000000002',
  TIME_R: '4f8c0000-1f0a-4c1e-9b2d-000000000003',
  FACE: '4f8c0000-1f0a-4c1e-9b2d-000000000004',
  DATA: '4f8c0000-1f0a-4c1e-9b2d-000000000005',
  STATUS: '4f8c0000-1f0a-4c1e-9b2d-000000000006',
  BRIGHT: '4f8c0000-1f0a-4c1e-9b2d-000000000007',  // v0.3.14
  DIAL: '4f8c0000-1f0a-4c1e-9b2d-000000000008',    // v0.3.14
}
const DEVICE_NAME = 'PixelClock'

// 帧常量（与固件 face_remote.h 一致）
const FRAME_BYTES = 64 * 64 * 2  // 8192
const CMD_DATA = 0x01
const CMD_COMMIT = 0x02

function u32le(n) {
  const b = new ArrayBuffer(4)
  new DataView(b).setUint32(0, n >>> 0, true) // little-endian
  return b
}

function u8(n) {
  const b = new ArrayBuffer(1)
  new DataView(b).setUint8(0, n & 0xff)
  return b
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

// CRC16-XMODEM（poly 0x1021, init 0x0000）——与固件 RemoteFace::crc16 一致
function crc16(bytes) {
  let crc = 0
  for (let i = 0; i < bytes.length; i++) {
    crc = (crc ^ ((bytes[i] & 0xff) << 8)) & 0xffff
    for (let b = 0; b < 8; b++) {
      crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff
    }
  }
  return crc & 0xffff
}

class BleManager {
  constructor() {
    this.deviceId = null
    this.connected = false
    this.chars = {}
    this.found = []
    this._onFound = null
    this._mtu = 185                 // 协商后的 MTU（默认按 iOS 常见值兜底）
    this._statusWaiter = null       // 等待 STATUS 通知的 {resolve, reject, timer}
  }

  init() {
    if (this._initPromise) return this._initPromise
    this._initPromise = new Promise((resolve, reject) => {
      wx.openBluetoothAdapter({
        success: () => {
          // 全局监听：STATUS 特征通知在这里落账
          wx.onBLECharacteristicValueChange((res) => {
            if (
              res.characteristicId &&
              res.characteristicId.toLowerCase() === CH.STATUS
            ) {
              this._onStatusNotify(res.value)
            }
          })
          resolve()
        },
        fail: (e) => {
          this._initPromise = null   // 失败允许重试（用户去开蓝牙）
          reject(e)
        },
      })
    })
    return this._initPromise
  }

  // scan/connect 前的懒初始化兜底
  async _ensureInit() {
    try {
      await this.init()
    } catch (e) {
      throw new Error('蓝牙适配器打开失败，请检查手机蓝牙是否开启')
    }
  }

  scan(timeout = 5000) {
    return new Promise((resolve, reject) => {
      this.found = []
      this._onFound = (res) => {
        const hit = (res.devices || []).find(
          (d) => (d.name === DEVICE_NAME || d.localName === DEVICE_NAME)
        )
        if (hit && !this.found.find((x) => x.deviceId === hit.deviceId)) {
          this.found.push({
            deviceId: hit.deviceId,
            name: hit.name || hit.localName,
            RSSI: hit.RSSI,
          })
        }
      }
      this._ensureInit()
        .then(() => {
          wx.onBluetoothDeviceFound(this._onFound)
          wx.startBluetoothDevicesDiscovery({
            services: [],
            allowDuplicatesKey: false,
            success: () => {
              setTimeout(() => {
                wx.stopBluetoothDevicesDiscovery()
                resolve(this.found)
              }, timeout)
            },
            fail: (e) => reject(e),
          })
        })
        .catch(reject)
    })
  }

  connect(deviceId) {
    return new Promise((resolve, reject) => {
      wx.createBLEConnection({
        deviceId,
        success: () => {
          this.deviceId = deviceId
          this._discover().then(resolve).catch(reject)
        },
        fail: reject,
      })
    })
  }

  _discover() {
    return new Promise((resolve, reject) => {
      wx.getBLEDeviceServices({
        deviceId: this.deviceId,
        success: (sres) => {
          const svc = (sres.services || []).find(
            (s) => s.uuid.toLowerCase() === SERVICE_UUID
          )
          if (!svc) return reject(new Error('未找到 PixelClock 服务'))
          wx.getBLEDeviceCharacteristics({
            deviceId: this.deviceId,
            serviceId: SERVICE_UUID,
            success: (cres) => {
              this.chars = {}
              ;(cres.characteristics || []).forEach((c) => {
                const u = c.uuid.toLowerCase()
                if (u === CH.TIME) this.chars.time = c.uuid
                else if (u === CH.TIME_R) this.chars.timeR = c.uuid
                else if (u === CH.FACE) this.chars.face = c.uuid
                else if (u === CH.DATA) this.chars.data = c.uuid
                else if (u === CH.STATUS) this.chars.status = c.uuid
                else if (u === CH.BRIGHT) this.chars.bright = c.uuid
                else if (u === CH.DIAL) this.chars.dial = c.uuid
              })
              this.connected = true
              resolve({ deviceId: this.deviceId })
            },
            fail: reject,
          })
        },
        fail: reject,
      })
    })
  }

  _write(charUuid, buffer) {
    return new Promise((resolve, reject) => {
      if (!this.connected || !charUuid) return reject(new Error('未连接或未发现特征'))
      wx.writeBLECharacteristicValue({
        deviceId: this.deviceId,
        serviceId: SERVICE_UUID,
        characteristicId: charUuid,
        value: buffer,
        success: resolve,
        fail: reject,
      })
    })
  }

  // 连上即校时（CST-8 由固件处理，这里给 UTC 秒即可）
  syncTime() {
    const now = Math.floor(Date.now() / 1000)
    return this._write(this.chars.time, u32le(now))
  }

  // 切换固件内置表盘：0=TEST 1=CLOCK 2=PLASMA 3=REMOTE(APP 推送)
  selectFace(idx) {
    return this._write(this.chars.face, u8(idx))
  }

  // v0.3.14：设置亮度 0~255（BRIGHT 特征；旧固件无此特征会抛错）
  setBrightness(v) {
    v = Math.max(0, Math.min(255, v | 0))
    return this._write(this.chars.bright, u8(v))
  }

  // v0.3.14：播放设备 FS 表盘（DIAL 特征，string stem）
  // 体验版小程序无 HTTP 域名通道，表盘播放走这里；列表见 dials 页缓存
  playDial(name) {
    name = String(name || '').trim()
    if (!name) return Promise.reject(new Error('表盘名为空'))
    // string → ArrayBuffer（BLE 写 UTF-8 字节）
    const buf = new ArrayBuffer(name.length)
    const view = new Uint8Array(buf)
    for (let i = 0; i < name.length; i++) view[i] = name.charCodeAt(i)
    return this._write(this.chars.dial, buf)
  }

  // ---------------- M3：推送完整表盘 ----------------

  // 尽力协商大 MTU（Android 有效；iOS 自动协商，失败按 185 兜底）
  _negotiateMTU() {
    return new Promise((resolve) => {
      wx.setBLEMTU({
        deviceId: this.deviceId,
        mtu: 247,
        success: (res) => {
          this._mtu = res && res.mtu ? res.mtu : 247
          resolve()
        },
        fail: () => {
          this._mtu = 185
          resolve()
        },
      })
    })
  }

  _chunkSize() {
    // ATT 写 payload 上限 = MTU-3，再留 4 字节协议头
    if (this._mtu >= 200) return 200
    if (this._mtu >= 100) return 160
    return 16 // MTU 23 兜底：4+16 = 20，正好一个默认包
  }

  // 打开 STATUS 特征通知
  _enableStatusNotify() {
    return new Promise((resolve, reject) => {
      if (!this.chars.status) return reject(new Error('设备无 STATUS 特征（固件版本过旧，请升级到 v0.2.0+）'))
      wx.notifyBLECharacteristicValueChange({
        deviceId: this.deviceId,
        serviceId: SERVICE_UUID,
        characteristicId: this.chars.status,
        state: true,
        success: () => resolve(),
        fail: reject,
      })
    })
  }

  _onStatusNotify(value) {
    const w = this._statusWaiter
    if (!w || !value || !value.byteLength) return
    const st = new DataView(value).getUint8(0)
    this._statusWaiter = null
    if (w.timer) clearTimeout(w.timer)
    w.resolve(st)
  }

  // 推送一帧表盘；onProgress(0~100) 进度回调
  // 成功时固件已自动切换到 REMOTE 表盘
  async pushFace(face, onProgress) {
    if (!this.connected) throw new Error('未连接设备')
    if (!face || !face.preview) throw new Error('表盘数据缺失')
    if (!this.chars.data) throw new Error('未发现 DATA 特征')

    const bytes = render.toRGB565(face.preview)
    if (bytes.length !== FRAME_BYTES) throw new Error('帧大小异常')
    const crc = crc16(bytes)

    await this._negotiateMTU()
    await this._enableStatusNotify()

    // 等固件的 STATUS 通知（提交后确认）
    const confirmed = new Promise((resolve, reject) => {
      this._statusWaiter = {
        resolve,
        reject,
        timer: setTimeout(() => {
          this._statusWaiter = null
          reject(new Error('设备确认超时（8s）'))
        }, 8000),
      }
    })

    const chunk = this._chunkSize()
    let off = 0
    while (off < bytes.length) {
      const len = Math.min(chunk, bytes.length - off)
      const pkt = new Uint8Array(4 + len)
      pkt[0] = CMD_DATA
      pkt[1] = off & 0xff
      pkt[2] = (off >> 8) & 0xff
      pkt[3] = len
      pkt.set(bytes.subarray(off, off + len), 4)
      await this._write(this.chars.data, pkt.buffer)
      off += len
      if (onProgress) onProgress(Math.min(99, Math.floor((off / bytes.length) * 100)))
      if (off < bytes.length) await sleep(12) // 让 BLE 栈喘口气，防拥塞丢包
    }

    // 提交（带 CRC）
    const tail = new Uint8Array([CMD_COMMIT, crc & 0xff, (crc >> 8) & 0xff])
    await this._write(this.chars.data, tail.buffer)

    const st = await confirmed
    if (onProgress) onProgress(100)
    if (st !== 2) {
      const why = st === 3 ? 'CRC 校验失败（传输损坏，请重试）'
                : st === 4 ? '设备中止了本次推送（超时）'
                : '设备返回状态 ' + st
      throw new Error(why)
    }
    return st
  }

  disconnect() {
    this._statusWaiter = null
    if (!this.deviceId) return Promise.resolve()
    return new Promise((resolve) => {
      wx.closeBLEConnection({
        deviceId: this.deviceId,
        success: () => {
          this.connected = false
          this.deviceId = null
          resolve()
        },
        fail: () => {
          this.connected = false
          this.deviceId = null
          resolve()
        },
      })
    })
  }
}

module.exports = new BleManager()
