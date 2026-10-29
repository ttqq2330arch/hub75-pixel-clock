// utils/faces.js — 表盘静态数据访问（本地数据，零服务器）
// 注意：require .json 在微信小程序里不可靠（会导致 app.js 启动崩溃、全页面
// "has not been registered yet"），所以改用生成的 JS 模块 faces-index.js
const index = require('../data/faces-index.js')

function list() {
  return index.faces
}

function getFace(id) {
  return index.faces.find((f) => f.id === id) || null
}

function categories() {
  const s = new Set(index.faces.map((f) => f.category))
  return Array.from(s)
}

module.exports = { list, getFace, categories, index }
