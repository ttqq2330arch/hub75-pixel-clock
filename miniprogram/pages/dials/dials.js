// pages/dials/dials.js — 设备 FS 表盘库：列表 + RGB565 预览 + 播放/删除
const api = require('../../utils/api.js')
const render = require('../../utils/render.js')

Page({
  data: {
    dials: [],
    loading: true,
    msg: '',
    msgType: '',
  },

  onShow() {
    this.load()
  },

  _toast(m, t) {
    this.setData({ msg: m, msgType: t || 'ok' })
    clearTimeout(this._mt)
    this._mt = setTimeout(() => this.setData({ msg: '' }), 2500)
  },

  async load() {
    this.setData({ loading: true })
    try {
      const d = await api.listDials()
      const dials = (d.dials || []).slice().sort((a, b) =>
        a.n.localeCompare(b.n))
      // setData 渲染完成后再取 canvas 节点（24 个 cell 可能超过 60ms）
      this.setData({ dials, loading: false }, () => {
        setTimeout(() => this._drawAll(), 30)
      })
    } catch (e) {
      this.setData({ loading: false, msg: '加载失败：' + e.message, msgType: 'bad' })
    }
  },

  _drawAll() {
    const q = wx.createSelectorQuery()
    const n = this.data.dials.length
    for (let i = 0; i < n; i++) q.select('#cv-' + i).fields({ node: true, size: true })
    q.exec((res) => {
      if (!res) return
      // 限量并发：板子 lwIP 并发 TCP PCB 约 16 个，24 个表盘一次全发
      // preview 请求会把连接挤掉（静默失败 → 空白预览格）。4 个一批最稳。
      this._inflight = 0
      let i = 0
      const next = () => {
        while (i < res.length && this._inflight < 4) {
          const node = res[i] && res[i].node
          const name = this.data.dials[i] && this.data.dials[i].n
          i++
          if (!node || !name) continue
          node.width = 64
          node.height = 64
          this._inflight++
          api.previewDial(name).then(
            (b64) => render.drawRGB565(node, b64),
            () => {}
          ).then(() => {
            this._inflight--
            next()
          })
        }
      }
      next()
    })
  },

  async onPlay(e) {
    const n = e.currentTarget.dataset.n
    try {
      await api.playDial(n)
      this._toast('已播放：' + n)
    } catch (err) {
      this._toast('播放失败：' + err.message, 'bad')
    }
  },

  onDel(e) {
    const n = e.currentTarget.dataset.n
    wx.showModal({
      title: '删除表盘',
      content: '确定删除「' + n + '」？\n（设备上的 .rgb565 与 meta 一并删除，不可恢复）',
      confirmText: '删除',
      confirmColor: '#e64340',
      success: (r) => {
        if (r.confirm) this._del(n)
      },
    })
  },
  async _del(n) {
    try {
      await api.delDial(n)
      this._toast('已删除：' + n)
      this.load()
    } catch (err) {
      this._toast('删除失败：' + err.message, 'bad')
    }
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },
})
