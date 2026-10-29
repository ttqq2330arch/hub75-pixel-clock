# HUB75 像素时钟 · 微信小程序控制端

配套固件 `hub75-pixel-clock`（v0.3.13+，ESP32-S3 + 64×64 HUB75）。
通过家庭 WiFi 直连板子，控制亮度、切换表盘、管理设备内表盘库、推送本地表盘。

## 快速开始（3 步）

1. **打开微信开发者工具** → 导入项目 → 选择本目录（`miniprogram/`）
   - AppID：项目里已带测试态 AppID（`wxd4ef8240f24c46ce`），也可换自己的
2. **必须关闭域名校验**（否则打不开局域网 IP）：
   详情 → 本地设置 → 勾选「**不校验合法域名、web-view（域名、TLS 版本以及 HTTPS 证书）**」
3. **编译预览**：手机与板子连**同一个 WiFi**，点「预览」扫码即可用
   - 板子默认地址 `192.168.1.52`（在「控制台」页可改，自动记住）

## 功能

| 页面 | 能力 |
|---|---|
| 控制台 | 设备在线状态/信号强度、亮度滑块 + 预设（10/30/60/100%/息屏）、固件表盘切换、播放/保存 flash 动画 |
| 表盘库 | 设备 FS 内全部表盘网格预览（64×64 像素风）、点击播放、删除（二次确认）、下拉刷新 |
| 表盘商店 | 本地 7 个像素表盘，一键推送到设备（HTTP 分块上传）并立即播放 |
| 详情/蓝牙 | 表盘推送进度；「蓝牙模式」为旧 BLE 通道，当前固件关闭 BLE，页面有说明 |

## ⚠️ 蓝牙通道当前不可用

固件侧 `src/config.h` 的 `ENABLE_BLE=0`（BLE + WiFi 共存会挤爆 lwIP 堆），
`ble_service.cpp` 整块不编译，板子不广播 GATT 服务，小程序扫描必然找不到设备。

因此首页的蓝牙卡片与「蓝牙模式」入口**默认隐藏**（`pages/home/home.js` 顶部的
`const BLE_ENABLED = false`）。

**要启用蓝牙：** 把固件 `src/config.h` 的 `ENABLE_BLE` 改为 `1` 重新编译烧录，
再把小程序 `pages/home/home.js` 的 `BLE_ENABLED` 改为 `true` —— 小程序端无需其他改动。

## 技术要点

- **通信**：全部走 WiFi HTTP（`wx.request` → 板子 `WebServer`），与网页版
  `push_page_template.html` 同一套 API：`/status` `/brightness` `/face`
  `/diallist` `/dialpreview` `/dialplay` `/dialdel` `/dialup` `/animload` `/animsave`
- **预览图**：`/dialpreview` 返回首帧 8192B RGB565 小端 base64 →
  `utils/render.js` 的 `drawRGB565()` 解成 ImageData 画上 canvas 2d
- **上传**：`/dialup` 裸 hex 分块（4096B/块，`Content-Type: text/plain`，
  `final=1&play=1` 收尾即播）
- **参数约定**：POST 参数一律走 URL query（板子 WebServer 不解析 JSON body）
- **IP 记忆**：`storage` 键 `pixelclock_ip`，控制台顶部可改

## 目录

```
miniprogram/
├── app.js / app.json / app.wxss
├── pages/
│   ├── home/    控制台（tab）
│   ├── dials/   设备表盘库（tab）
│   ├── store/   本地表盘商店（tab）
│   ├── detail/  推送详情
│   └── devices/ 蓝牙模式（旧通道）
├── utils/
│   ├── api.js     WiFi HTTP 封装（含 IP 管理）
│   ├── render.js  RGB565 ↔ canvas
│   ├── faces.js   本地表盘数据
│   └── ble.js     旧蓝牙通道
└── data/faces/    7 个本地表盘（#rrggbb 像素数组）
```

## 常见问题

- **小程序转圈/请求失败**：90% 是没关域名校验（见步骤 2），或手机与板子不在同一网段
- **改表盘要重编译小程序吗**：不用。改 `data/faces/` 后重新导入即可
- **想公网控制**：局域网方案不适用于校外网络；需要时再谈内网穿透/云方案
