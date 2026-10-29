# HUB75 像素时钟 · 表盘商店小程序方案

> 配套你自有硬件（HUB75 64×64 P2.5 + ESP32-S3 N16R8）的表盘管理小程序。
> 不是 HOKA 复刻，是"自己造生态"那条路——手机浏览表盘 → 一键推到屏上。
> 与固件接口严格对齐 `src/ble_service.cpp` 与 `docs/watchface-format.md`。

---

## 1. 产品定位

| 项 | 说明 |
|---|---|
| 它是什么 | 你 HUB75 时钟的**表盘管理 + 推送工具**，手机端 |
| 用户 | 你自己先用；后续可分享给同好（同款硬件） |
| 核心闭环 | 商店看表盘 → 点详情预览 → 蓝牙推送到 ESP32 → 屏上亮起来 |
| 与 HOKA 区别 | HOKA 是给自家硬件卖表盘；你是**自用 + 开源共享**，不碰支付红线 |

---

## 2. 微信主体与合规边界（先说清，免得白做）

| 主体 | 能做 | 不能做 |
|---|---|---|
| **个人主体**（你现在的默认） | 免费表盘库、BLE 推送、Canvas 预览 | ❌ 虚拟支付（iOS 全禁、安卓受限） |
| **企业主体**（以后想赚钱再注册） | 上面的 + 付费表盘、提现 | 需要营业执照 + 微信支付商户号 |

**本方案按"个人主体 + 免费表盘库"设计**，不碰支付。要商业化再说，先把闭环跑通。

---

## 3. 整体架构

```
┌──────────────────────────── 微信小程序 ────────────────────────────┐
│  表盘商店(store)   表盘详情(detail)   我的设备(devices)   关于(about) │
│        │                  │                     │                     │
│        └──── 选表盘 ───────┴──── 推送到设备 ─────┘                     │
└───────────────────────────────┬─────────────────────────────────────┘
                                 │ 微信 BLE API（wx.openBluetoothAdapter…）
                                 ▼
                   ┌──────── ESP32-S3 固件 ────────┐
                   │ 服务 4f8c…0001                │
                   │  TIME  (写)  ✅ 校时 uint32 LE │
                   │  FACE  (写)  ✅ 切盘 uint8      │
                   │  DATA  (写)  ⏳ M3 推表盘帧    │
                   └───────────────────────────────┘
                                 │
                   ┌──── 可选后端（M4 才要）────┐
                   │ 表盘库 manifest+frames      │
                   │ 静态 JSON / COS 对象存储    │
                   └────────────────────────────┘
```

---

## 4. 页面与功能清单

| 页面 | 功能 | 优先级 |
|---|---|---|
| `pages/store` | 表盘网格（缩略图、分类、搜索框，照 HOKA 那张截图的版式） | P0 |
| `pages/detail` | 大图 + **Canvas 64×64 动画预览** + "推送到设备"按钮 | P0 |
| `pages/devices` | BLE 扫描/连接、已连设备、时间同步、表盘切换列表 | P0 |
| `pages/about` | 版本、表盘投稿方式、开源协议 | P1 |
| `pages/upload` | 创作者上传表盘（**需后端，M4 才做**） | P2 |

store 页版式（照你截图还原手感）：

```
┌─────────────────────────┐
│  🔍 [ 搜表盘……        ] │   ← 搜索框
│ ┌────┐ ┌────┐ ┌────┐   │
│ │ 猫 │ │高达│ │吃豆│   │   ← 表盘网格（每格 64×64 预览缩放）
│ └────┘ └────┘ └────┘   │
│ ┌────┐ ┌────┐ ┌────┐   │
│ │ 钟 │ │ 星 │ │ 火 │   │
│ └────┘ └────┘ └────┘   │
│                    [卖] │   ← 投稿入口（M4）
└─────────────────────────┘
```

---

## 5. 技术栈

- **原生微信小程序**（WXML/WXSS/JS）。不引 uni-app/mpvue——BLE + Canvas 原生 API 最稳，跨端框架反而添坑。
- **预览**：Canvas 2D，把 64×64 像素网格放大渲染（每像素画成 6~8px 方块），模拟点阵质感；透明背景像素不绘制，露出底色。
- **后端（M4 才要）**：最小静态服务即可——一个 `faces-index.json` 列表 + 每个表盘的 `manifest.json`/`frames.bin`/预览图，丢 COS 免费额度或 GitHub Pages 都行。
- **表盘生成器**：`tools/mkface.py`，把 PNG/GIF → `manifest.json` + `frames.bin`（RGB565 little-endian），统一像素格式，给创作者和官方内置表盘共用。

---

## 6. BLE 对接（与固件一一对应）

固件现状（`ble_service.cpp`）：设备名 **`PixelClock`**，服务 UUID `4f8c0000-1f0a-4c1e-9b2d-000000000001`。

| 特征 | UUID 末段 | 小程序动作 |
|---|---|---|
| TIME（写） | …0002 | 连上即 `writeBLECharacteristicValue`，uint32 LE 当前 Unix 秒 → 校时 |
| TIME_READ（读） | …0003 | 可选，轮询读回确认时间已同步 |
| FACE（写） | …0004 | `writeBLECharacteristicValue`，uint8 表盘索引 → 切换 |
| DATA（写） | …0005 | **M3 后**：按 `watchface-format.md` 0xA5 帧协议推表盘 |

**连接流程**（微信 API 顺序）：
```
openBluetoothAdapter → startBluetoothDevicesDiscovery
  → onBluetoothDeviceFound（按名称 PixelClock / 服务UUID 过滤）
  → createBLEConnection → stopBluetoothDevicesDiscovery
  → getBLEDeviceServices → getBLEDeviceCharacteristics
  →（DATA 需 notify/indicate 监听 ACK 0x04 / NAK 0x81 / Done 0x82）
  → setBLEMTU 512（提速，iOS 默认 20 字节太慢）
```

**推送表盘帧协议**（M3 实现，详见 watchface-format.md §2）：
```
小程序                                   固件
 0xA5 01 START(manifest JSON) ───────▶  校验/擦 Flash 目标槽
 ◀─────────────────────────────────  0xA5 04 seq=0xFF (ready)
 0xA5 02 DATA seq=0..N (frames 切片) ─▶  校验 crc16 → 写 Flash → 回 0x04 seq
 0xA5 03 END count=N ────────────────▶  校验整包 CRC32 → 回 0x82 "id"
```

---

## 7. 表盘库 & 内容策略（这是"商店"的灵魂）

- **冷启动不靠 UGC**：我先给你生成 **8~10 个原创表盘**（像素风、透明背景可叠加时间），一上架货架就是满的。
- **仓库结构**（小程序读 CDN 列表）：
  ```
  faces-index.json
  faces/
    ├── cat_tea/        preview.png + manifest.json + frames.bin
    ├── gundam/         …
    └── pacman/         …
  ```
- 表盘格式严格走 `docs/watchface-format.md`，与固件解包一致，推送即用。

---

## 8. 里程碑

| 里程碑 | 内容 | 依赖 | 状态 |
|---|---|---|---|
| **M1** | 小程序骨架：store/detail/devices 三页 + BLE 连接/校时 + Canvas 预览 + 6 个内置表盘静态数据 | 无 | ✅ 已建（2026-10-21） |
| **M2** | 表盘切换：FACE 特征切内置表盘 + Canvas 预览联动 | M1 | 代码就绪，待真机 BLE 实测 |
| **M3** | 固件补 DATA 回调 + 小程序推送完整表盘（帧协议） | 需改固件 + 小程序 | 接口已留（pushFace 抛 M3 提示） |
| **M4** | 后端表盘库 + 投稿上传页（可选） | 企业主体/服务器（按需） | 未启动 |

### M1 已交付文件树

```
miniprogram/
├── project.config.json        # appid=touristappid（开发用测试号，真机调试换你自己的）
├── app.json / app.js / app.wxss
├── utils/
│   ├── ble.js                # BLE 管理器（TIME/FACE 已实现，pushFace 留 M3 接口）
│   ├── faces.js              # 读本地 faces-index.json
│   └── render.js             # 64×64 像素 → Canvas 放大渲染
├── pages/
│   ├── store/                # 表盘商店（分类筛选 + 网格 + 每卡 Canvas 预览）
│   ├── detail/               # 表盘详情（大图预览 + 推送到设备）
│   └── devices/              # 我的设备（BLE 扫描/连接/校时/切盘）
└── data/
    ├── faces-index.json      # 6 个内置表盘（含 64×64 预览像素，零网络）
    └── faces/<id>/{manifest,preview}.json
tools/
├── gen_faces.py              # 生成内置演示表盘（纯标准库）
└── mkface.py                 # 图片/GIF → 表盘包（需 pillow）
```

> 校验：全部 JSON 解析通过、全部 JS `node --check` 语法通过。小程序需在微信开发者工具内编译（沙箱无 DevTools，未做真机运行验证）。

---

## 9. 我现在能直接开干的部分

- ✅ 小程序工程骨架（三页 + BLE 连接 + Canvas 预览）
- ✅ `tools/mkface.py` 表盘生成器
- ✅ 8~10 个原创表盘素材（直接填满货架）

---

## 10. 待你拍板的 3 个点

1. **AppID**：用你自己的微信小程序 AppID（个人主体），还是先用**测试号**跑通流程？
2. **表盘库托管**：先用我本地生成的**静态 JSON**（零服务器成本），还是直接上 COS/GitHub Pages？
3. **是否现在就建 M1 工程**？还是先把硬件焊完点亮、BLE 实测通了再上小程序？

> 建议：硬件点亮（TEST 图案）→ M1 小程序连上校时 → 再堆表盘。链路从最底层验证起，每段都有据可查。
