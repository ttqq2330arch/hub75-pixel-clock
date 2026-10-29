const facesApi = require('../../utils/faces.js')
const render = require('../../utils/render.js')

Page({
  data: {
    cats: ['全部'],
    activeCat: '全部',
    faces: [],
  },
  onLoad() {
    const cats = ['全部', ...facesApi.categories()]
    this.setData({ cats, faces: facesApi.list() })
  },
  onReady() {
    this._drawAll()
  },
  _drawAll() {
    this.data.faces.forEach((f) => {
      wx.createSelectorQuery()
        .select('#cv-' + f.id)
        .fields({ node: true, size: true })
        .exec((res) => {
          if (res && res[0] && res[0].node) {
            render.drawPreview(res[0].node, f.preview, 2, f.bg_mode)
          }
        })
    })
  },
  onCat(e) {
    const cat = e.currentTarget.dataset.cat
    const list =
      cat === '全部'
        ? facesApi.list()
        : facesApi.list().filter((f) => f.category === cat)
    this.setData({ activeCat: cat, faces: list }, () => this._drawAll())
  },
  onTap(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.currentTarget.dataset.id })
  },
})
