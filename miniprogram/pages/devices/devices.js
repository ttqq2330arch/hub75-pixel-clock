const app = getApp()
const ble = require('../../utils/ble.js')

// 蓝牙通道可用性：与固件 src/config.h 的 ENABLE_BLE 保持一致。
// 固件 ENABLE_BLE=0 时不编译 ble_service.cpp，板子没有 GATT 服务，本页扫不到任何设备。
const BLE_ENABLED = false

// 固件内置表盘索引（src/faces.cpp: registerBuiltins）
const FIRMWARE_FACES = [
  { idx: 0, name: 'TEST 接线验证' },
  { idx: 1, name: 'CLOCK 像素时钟' },
  { idx: 2, name: 'PLASMA 等离子' },
  { idx: 3, name: 'REMOTE 远程表盘（APP 推送）' },
]

Page({
  data: {
    devices: [],
    device: null,
    status: '',
    fwFaces: FIRMWARE_FACES,
    bleEnabled: BLE_ENABLED,
  },
  onLoad() {
    this.setData({ device: app.globalData.device })
  },
  onUnload() {
    // 离开设备页主动断开：微信小程序退后台/杀进程时不释放 GATT 连接，
    // 设备会卡在"已连接不广播"状态，下次扫描什么都扫不到
    ble.disconnect()
    app.globalData.device = null
  },
  async scan() {
    this.setData({ status: '扫描中…' })
    try {
      const devs = await ble.scan(4000)
      this.setData({
        devices: devs,
        status: devs.length ? '找到 ' + devs.length + ' 个设备' : '未找到设备',
      })
    } catch (e) {
      this.setData({ status: '扫描失败：' + (e.errMsg || e.message || e) })
    }
  },
  async connect(e) {
    const id = e.currentTarget.dataset.id
    this.setData({ status: '连接中…' })
    try {
      await ble.connect(id)
      const dev =
        ble.found.find((d) => d.deviceId === id) || { deviceId: id, name: 'PixelClock' }
      app.globalData.device = dev
      this.setData({ device: dev, status: '已连接，校时中…' })
      await ble.syncTime()
      this.setData({ status: '已连接并校时 ✓' })
    } catch (e) {
      this.setData({ status: '连接失败：' + (e.errMsg || e.message || e) })
    }
  },
  async sync() {
    try {
      await ble.syncTime()
      this.setData({ status: '已校时 ✓' })
    } catch (e) {
      this.setData({ status: '校时失败：' + (e.errMsg || e.message || e) })
    }
  },
  async sel(e) {
    const idx = e.currentTarget.dataset.idx
    try {
      await ble.selectFace(idx)
      this.setData({ status: '已切换表盘 #' + idx })
    } catch (e) {
      this.setData({ status: '切换失败：' + (e.errMsg || e.message || e) })
    }
  },
  disconnect() {
    ble.disconnect().then(() => {
      app.globalData.device = null
      this.setData({ device: null, status: '已断开' })
    })
  },
})
