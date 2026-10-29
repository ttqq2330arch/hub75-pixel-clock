// pages/home/home.js — 控制台：设备连接 + 亮度 + 固件表盘 + flash 动画
// v0.3.14：加蓝牙控制卡（体验版小程序被 request 域名限制，BLE 是免域名通道）
// v0.3.24：固件侧 BLE 已关闭（ENABLE_BLE=0，src/config.h），BLE 通道当前不可用。
//          保留全部 BLE 代码与开关常量，固件改回 ENABLE_BLE=1 即可原地复活，无需改前端。
const api = require('../../utils/api.js')
const ble = require('../../utils/ble.js')

// 蓝牙通道可用性：必须与固件 src/config.h 的 ENABLE_BLE 保持一致。
// 固件 ENABLE_BLE=0 → ble_service.cpp 整块不编译 → 板子根本没有 GATT 服务，
// 小程序扫描永远找不到 PixelClock。此处置 false 以隐藏入口，避免用户点了才知道连不上。
const BLE_ENABLED = false

// 固件内置表盘索引（src/faces.cpp: registerBuiltins）
const FIRMWARE_FACES = [
  { idx: 0, name: 'TEST 接线验证' },
  { idx: 1, name: 'CLOCK 像素时钟' },
  { idx: 2, name: 'PLASMA 等离子' },
  { idx: 3, name: 'REMOTE 远程表盘' },
]

// 蓝牙快捷播放（设备 FS 表盘名）
const BLE_QUICK_DIALS = ['mario-clock', 'mario-clock-burst']

Page({
  data: {
    ip: '',
    st: { online: false, rssi: 0, host: '', bright: 0 },
    bright: 128,
    brightPct: 50,
    dialCount: 0,
    fwFaces: FIRMWARE_FACES,
    quickDials: BLE_QUICK_DIALS,
    animInfo: '',
    msg: '',
    msgType: '',   // ok | bad
    // 蓝牙
    bleEnabled: BLE_ENABLED,
    bleConnected: false,
    bleBusy: false,
    bleStatus: '',
    bleBright: 128,
  },

  onLoad() {
    this.setData({ ip: api.ip() })
  },
  onShow() {
    this._refresh()
    // 3s 轮询设备状态；onHide 清除（后台不请求，省电也避免堆请求）
    this._timer = setInterval(() => this._refresh(), 3000)
  },
  onHide() {
    if (this._timer) clearInterval(this._timer)
    this._timer = null
  },
  onUnload() {
    if (this._timer) clearInterval(this._timer)
    this._timer = null
  },

  _toast(m, t) {
    this.setData({ msg: m, msgType: t || 'ok' })
    clearTimeout(this._mt)
    this._mt = setTimeout(() => this.setData({ msg: '' }), 2500)
  },

  async _refresh() {
    try {
      const st = await api.getStatus()
      this._offHinted = false
      this.setData({
        st: {
          online: true,
          rssi: st.rssi || 0,
          host: st.host || '',
          bright: st.bright || 0,
        },
        bright: typeof st.bright === 'number' ? st.bright : this.data.bright,
      })
      this.setData({ brightPct: Math.round((this.data.bright / 255) * 100) })
    } catch (e) {
      this.setData({ 'st.online': false })
      // HTTP 通道不通时的引导：仅在 BLE 通道可用时才引导去蓝牙
      // （BLE 不经过 WiFi/HTTP，板子 HTTP 假死也能控；但固件关 BLE 时这条建议是错的）
      if (BLE_ENABLED && !this.data.bleConnected && !this._offHinted) {
        this._offHinted = true
        this._toast('HTTP 连不上设备，可用下方蓝牙控制', 'bad')
      } else if (!this._offHinted) {
        this._offHinted = true
        this._toast('连不上设备，请确认手机与板子在同一 WiFi、地址填对', 'bad')
      }
    }
    try {
      const d = await api.listDials()
      this.setData({ dialCount: (d.dials || []).length })
    } catch (e) { /* 静默 */ }
    this._loadAnimInfo()
  },

  onIpBlur(e) {
    const v = (e.detail.value || '').trim()
    const cur = api.setIp(v)
    this.setData({ ip: cur })
    this._toast('设备地址已保存：' + cur)
    this._refresh()
  },

  // slider 拖动过程中只本地预览，松手才下发（避免每像素一次 HTTP）
  onBrightChanging(e) {
    this.setData({ bright: e.detail.value, brightPct: Math.round((e.detail.value / 255) * 100) })
  },
  async onBrightChange(e) {
    const v = e.detail.value
    try {
      await api.setBrightness(v)
      this._toast('亮度 ' + Math.round((v / 255) * 100) + '%')
    } catch (err) {
      this._toast('设置失败：' + err.message, 'bad')
    }
  },
  async onPreset(e) {
    const v = parseInt(e.currentTarget.dataset.v, 10)
    this.setData({ bright: v, brightPct: Math.round((v / 255) * 100) })
    try {
      await api.setBrightness(v)
      this._toast(v === 0 ? '已息屏' : '亮度 ' + Math.round((v / 255) * 100) + '%')
    } catch (err) {
      this._toast('设置失败：' + err.message, 'bad')
    }
  },

  async onFace(e) {
    const idx = parseInt(e.currentTarget.dataset.idx, 10)
    try {
      await api.selectFace(idx)
      this._toast('已切换：' + FIRMWARE_FACES[idx].name)
    } catch (err) {
      this._toast('切换失败：' + err.message, 'bad')
    }
  },

  async onAnimLoad() {
    try {
      await api.animLoad()
      this._toast('已播放 flash 动画 ✓')
      this._loadAnimInfo()
    } catch (err) {
      this._toast('无 flash 动画或播放失败', 'bad')
    }
  },
  async onAnimSave() {
    try {
      await api.animSave()
      this._toast('已保存，重启后自动播放 ✓')
    } catch (err) {
      this._toast('保存失败：' + err.message, 'bad')
    }
  },
  async _loadAnimInfo() {
    try {
      const a = await api.animStatus()
      const parts = [a.frames + ' 帧', a.fps + ' fps']
      if (a.burst) parts.push('爆发')
      if (a.overlay) parts.push('时钟叠加')
      this.setData({ animInfo: parts.join(' · ') })
    } catch (e) { /* 静默：信息卡不影响主流程 */ }
  },

  goBle() {
    wx.navigateTo({ url: '/pages/devices/devices' })
  },
  goDials() {
    wx.switchTab({ url: '/pages/dials/dials' })
  },

  // ---------------- 蓝牙控制（体验版免域名通道） ----------------
  async bleConnect() {
    this.setData({ bleBusy: true, bleStatus: '扫描中…' })
    try {
      const devs = await ble.scan(4000)
      if (!devs.length) {
        this.setData({ bleStatus: '未找到 PixelClock（确认板子已上电且在附近）' })
        return
      }
      this.setData({ bleStatus: '连接中…' })
      await ble.connect(devs[0].deviceId)
      await ble.syncTime()
      this.setData({ bleConnected: true, bleStatus: '已连接并校时 ✓' })
    } catch (e) {
      this.setData({ bleStatus: '失败：' + (e.errMsg || e.message || e) })
    } finally {
      this.setData({ bleBusy: false })
    }
  },
  async bleDisconnect() {
    await ble.disconnect()
    this.setData({ bleConnected: false, bleStatus: '已断开' })
  },
  onBleBrightChanging(e) {
    this.setData({ bleBright: e.detail.value })
  },
  async onBleBrightChange(e) {
    const v = e.detail.value
    try {
      await ble.setBrightness(v)
      this._toast('亮度 ' + Math.round((v / 255) * 100) + '%')
    } catch (err) {
      this._toast('设置失败：' + (err.errMsg || err.message || err), 'bad')
    }
  },
  async onBleFace(e) {
    const idx = parseInt(e.currentTarget.dataset.idx, 10)
    try {
      await ble.selectFace(idx)
      this._toast('已切换：' + FIRMWARE_FACES[idx].name)
    } catch (err) {
      this._toast('切换失败：' + (err.errMsg || err.message || err), 'bad')
    }
  },
  async onBleQuick(e) {
    const n = e.currentTarget.dataset.n
    try {
      await ble.playDial(n)
      this._toast('播放：' + n)
    } catch (err) {
      this._toast('播放失败：' + (err.errMsg || err.message || err), 'bad')
    }
  },
})
