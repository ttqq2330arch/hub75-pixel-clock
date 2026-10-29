// pages/detail/detail.js — 本地表盘推送（HTTP /dialup hex 分块，v0.3.13 起弃 BLE）
// 旧版走 utils/ble.js 蓝牙分块；固件主通道早已是 WiFi HTTP（/dialup），
// 与网页版 push_page_template.html 的上传链路完全一致。
const facesApi = require('../../utils/faces.js')
const render = require('../../utils/render.js')
const api = require('../../utils/api.js')

Page({
  data: { face: null, status: '', progress: 0 },

  onLoad(q) {
    const face = facesApi.getFace(q.id)
    this.setData({ face })
    wx.setNavigationBarTitle({ title: face ? face.name : '表盘详情' })
  },

  _draw() {
    const f = this.data.face
    if (!f) return
    wx.createSelectorQuery()
      .select('#big')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (res && res[0] && res[0].node) {
          render.drawPreview(res[0].node, f.preview, 5, f.bg_mode)
        }
      })
  },
  onReady() {
    this._draw()
  },

  async push() {
    const f = this.data.face
    if (!f) return
    this.setData({ status: '转换像素数据…', progress: 0 })
    try {
      // 4096 个 #rrggbb → 8192B RGB565 小端（与固件 blit 逐位对应）
      const raw = render.toRGB565(f.preview)
      // 单帧图案 + 时钟叠加（经典模式默认位），推到设备 FS 并立即播放
      await api.uploadDial(f.id, raw, (p) => this.setData({ progress: p }), {
        fps: 1,
        overlay: 1,
        burst: 0,
      })
      this.setData({
        status: '已推送到「' + f.name + '」并开始播放 ✓',
        progress: 100,
      })
    } catch (e) {
      this.setData({ status: '推送失败：' + (e.message || e) })
    }
  },
})
