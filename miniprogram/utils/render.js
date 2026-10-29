// utils/render.js — 64x64 像素数组 ↔ canvas / RGB565 字节流
// preview: 4096 长度的 "#rrggbb" 数组；bg_mode=transparent 时跳过 "#000000"

const W = 64
const H = 64

function drawPreview(canvas, preview, scale, bgMode) {
  if (!canvas || !preview) return
  canvas.width = W * scale
  canvas.height = H * scale
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const c = preview[y * W + x]
      if (bgMode !== 'opaque' && c === '#000000') continue
      ctx.fillStyle = c
      ctx.fillRect(x * scale, y * scale, scale, scale)
    }
  }
}

// "#rrggbb" 数组 → RGB565 小端字节流（64*64*2 = 8192 字节）
// 与固件 src/face_remote.cpp 的 blit 逻辑逐位对应：
//   r>>3 <<11 | g>>2 <<5 | b>>3，低字节在前
function toRGB565(preview) {
  const out = new Uint8Array(W * H * 2)
  for (let i = 0; i < W * H; i++) {
    const hex = preview[i] || '#000000'
    const r = parseInt(hex.slice(1, 3), 16) || 0
    const g = parseInt(hex.slice(3, 5), 16) || 0
    const b = parseInt(hex.slice(5, 7), 16) || 0
    const v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    out[i * 2] = v & 0xff
    out[i * 2 + 1] = (v >> 8) & 0xff
  }
  return out
}

// 板子 /dialpreview 返回的首帧 base64（8192B RGB565 小端）→ canvas 2d
// canvas: wx.createSelectorQuery fields({node:true}) 拿到的 2d canvas 节点
// 用法：先 drawRGB565(node, b64)，再 ctx.putImageData(img, 0, 0)
function rgb565ToImageData(b64) {
  const buf = wx.base64ToArrayBuffer(b64)
  const src = new Uint16Array(buf)
  const img = {
    width: W, height: H,
    data: new Uint8ClampedArray(W * H * 4),
  }
  for (let i = 0; i < W * H; i++) {
    const v = src[i] || 0
    const r5 = (v >> 11) & 0x1f
    const g6 = (v >> 5) & 0x3f
    const b5 = v & 0x1f
    img.data[i * 4] = (r5 << 3) | (r5 >> 2)
    img.data[i * 4 + 1] = (g6 << 2) | (g6 >> 4)
    img.data[i * 4 + 2] = (b5 << 3) | (b5 >> 2)
    img.data[i * 4 + 3] = 255
  }
  return img
}

// 一站式：base64 RGB565 → 画到 2d canvas（节点），内部创建 ImageData
function drawRGB565(canvas, b64) {
  if (!canvas || !b64) return
  const ctx = canvas.getContext('2d')
  const img = rgb565ToImageData(b64)
  if (ctx.putImageData) {
    ctx.putImageData(img, 0, 0)
  } else {
    // 旧基础库兜底：手动逐像素 fillRect（慢但兼容）
    ctx.clearRect(0, 0, W, H)
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const i = (y * W + x) * 4
        ctx.fillStyle =
          'rgb(' + img.data[i] + ',' + img.data[i + 1] + ',' + img.data[i + 2] + ')'
        ctx.fillRect(x, y, 1, 1)
      }
    }
  }
}

module.exports = { drawPreview, toRGB565, drawRGB565, rgb565ToImageData, W, H }
