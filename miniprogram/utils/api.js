// utils/api.js — 像素时钟 WiFi HTTP 控制封装（v0.3.13 固件）
// 约定（与网页版 push_page_template.html 完全一致）：
//   - 所有参数走 URL query string，POST body 为空或裸 hex（text/plain）
//   - 板子 ESP32 WebServer 的 hasArg/arg 同时认 query 与 form body，
//     但小程序默认 application/json body 不会被解析，所以绝不拼 JSON body
// 设备 IP 存 storage（pixelclock_ip），默认 192.168.1.52，设置页可改

const KEY_IP = 'pixelclock_ip'
const DEF_IP = '192.168.1.52'

function ip() {
  return wx.getStorageSync(KEY_IP) || DEF_IP
}

function setIp(v) {
  v = String(v || '').trim()
  if (!v) v = DEF_IP
  wx.setStorageSync(KEY_IP, v)
  return v
}

function base() {
  return 'http://' + ip()
}

function req(path, opts) {
  opts = opts || {}
  return new Promise((resolve, reject) => {
    wx.request({
      url: base() + path,
      method: opts.method || 'GET',
      data: typeof opts.data === 'undefined' ? '' : opts.data,
      header: opts.header || {},
      timeout: opts.timeout || 10000,
      success: (r) => {
        if (r.statusCode >= 200 && r.statusCode < 300) {
          resolve(r.data)
        } else {
          reject(new Error('HTTP ' + r.statusCode))
        }
      },
      fail: (e) => reject(new Error(e.errMsg || '网络请求失败')),
    })
  })
}

// 读操作专用：失败自动重试 1 次（板子 MIN_MODEM 下偶发丢包/假死窗口，
// 盲等 3s 轮询的下一轮不如立刻补一发）。写操作不重试（避免亮度/播放双发）。
async function reqRetry(path, opts, tries) {
  tries = tries || 2
  let lastErr
  for (let i = 0; i < tries; i++) {
    try {
      return await req(path, opts)
    } catch (e) {
      lastErr = e
      if (i < tries - 1) await new Promise((r) => setTimeout(r, 1200))
    }
  }
  throw lastErr
}

const HEX = '0123456789abcdef'

// Uint8Array → hex 字符串（/dialup 上传用）
function toHex(u8, from, to) {
  let s = ''
  for (let i = from; i < to; i++) {
    s += HEX[u8[i] >> 4] + HEX[u8[i] & 0x0f]
  }
  return s
}

const api = {
  // ---- 设备信息 ----
  // GET /status → {ip, rssi, host, push, bright}
  getStatus: () => reqRetry('/status', { timeout: 5000 }),

  // ---- 亮度 ----
  // GET  /brightness          → {level:N}
  // POST /brightness?level=N  → {level:N}
  getBrightness: () => req('/brightness'),
  setBrightness: (v) => req('/brightness?level=' + Math.max(0, Math.min(255, v | 0)), { method: 'POST' }),

  // ---- 固件内置表盘（src/faces.cpp: registerBuiltins）----
  // POST /face?idx=N → "OK idx N"
  selectFace: (idx) => req('/face?idx=' + (idx | 0), { method: 'POST' }),

  // ---- FS 表盘库（LittleFS /dials/）----
  // GET  /diallist                  → {dials:[{n,c,f,o,b,s,m,x,y,x2,sc,fg}]}
  // GET  /dialpreview?name=<stem>   → 首帧 8192B 的 base64（text/plain）
  // POST /dialplay?name=<stem>      → "PLAY <stem>"
  // POST /dialdel?name=<stem>       → "DELETED <stem>"
  listDials: () => reqRetry('/diallist', { timeout: 6000 }),
  previewDial: (name) => reqRetry('/dialpreview?name=' + encodeURIComponent(name), { timeout: 6000 }),
  playDial: (name) => req('/dialplay?name=' + encodeURIComponent(name), { method: 'POST' }),
  delDial: (name) => req('/dialdel?name=' + encodeURIComponent(name), { method: 'POST' }),

  // ---- 动画背景 ----
  // POST /animload → 播放 flash 里的动画；POST /animsave → 当前动画存 flash
  animLoad: () => req('/animload', { method: 'POST' }),
  animSave: () => req('/animsave', { method: 'POST' }),
  // GET /animlist → 当前动画状态 {frames,fps,overlay,burst,...}
  animStatus: () => reqRetry('/animlist', { timeout: 5000 }),

  // ---- 上传表盘到设备（hex 分块，4096B/块）----
  // POST /dialup?name=&off=&len=[&fps=&overlay=&burst=][&final=1&play=1]
  //      body = 裸 hex 文本（text/plain），off=0 截断新建
  uploadDial(name, u8, onProgress, meta) {
    meta = meta || {}
    const fps = meta.fps || 6
    const ov = meta.overlay ? 1 : 0
    const burst = meta.burst ? 1 : 0
    const CHUNK = 4096
    const total = u8.length
    const q0 = '/dialup?name=' + encodeURIComponent(name) +
               '&fps=' + fps + '&overlay=' + ov + '&burst=' + burst
    const step = (off) => {
      if (off >= total) return Promise.resolve()
      const end = Math.min(off + CHUNK, total)
      const isFinal = end >= total
      let q = q0 + '&off=' + off + '&len=' + (end - off)
      if (isFinal) q += '&final=1&play=1'
      return req(q, {
        method: 'POST',
        data: toHex(u8, off, end),
        header: { 'Content-Type': 'text/plain' },
        timeout: 15000,
      }).then(() => {
        if (onProgress) onProgress(Math.round((end / total) * 100))
        return step(end)
      })
    }
    return step(0)
  },

  // ---- 多板部署：改主机名（重启后 hostname 生效）----
  setName: (name) => req('/setname?name=' + encodeURIComponent(name), { method: 'POST' }),
}

module.exports = api
module.exports.ip = ip
module.exports.setIp = setIp
module.exports.toHex = toHex
