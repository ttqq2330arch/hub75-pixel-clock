# 像素时钟 · Android APP（个人版）

ESP32-S3 + HUB75 64×64 像素时钟的**原生 Android 客户端**。

- **纯原生 Kotlin + Jetpack Compose**，不是 WebView 套壳
- **mDNS 自动发现**：开机后自动找到局域网里的板子，不用手输 IP
- **直连局域网 HTTP**：不经过任何云端服务器，板子离线也不影响其它功能
- **个人版**：debug 签名，直接侧载安装，不需要上架、不需要开发者资质

---

## 📸 界面

| 控制台 | 表盘库 | 设置 |
|---|---|---|
| 在线状态 / 信号强度 / 亮度 / 旋转 / 表盘商店 / WiFi 切换 | 板载表盘网格 + 缩略图 + 播放 + 删除 + 推送新表盘 | 板子地址 / 自动发现 / 主机名改名 / 关于 |

<p align="center">
  <img src="../docs/images/app-icon.png" alt="应用图标" width="120">
</p>

---

## 🔧 功能对照表

| 功能 | 固件接口 | 说明 |
|---|---|---|
| 设备状态 | `GET /status` | IP / 信号 / 主机名 / 亮度 / 旋转角 |
| 屏幕亮度 | `GET/POST /brightness` | 滑块 + 6 档预设 |
| 屏幕旋转 | `POST /rotate?v=0..3` | 0°/90°/180°/270° |
| 表盘商店 | `GET /faces`（gzip） | 6 款单帧表盘，点击即推送上屏 |
| 固件内置表盘 | `POST /face?idx=0..3` | 测试 / 时钟 / 等离子 / 远程 |
| 板载表盘库 | `GET /diallist` + `GET /dialpreview` | 缩略图网格、播放、删除 |
| 推送表盘 | `POST /dialup`（分片） | `.rgb565` 文件推到板子 flash 永久保存 |
| 即时单帧 | `POST /pushface` | 单帧直推 RAM，立刻显示 |
| 远程动画 | `GET /animlist`、`/animload`、`/animsave` | 载入 / 存到 flash |
| WiFi 切换 | `GET/POST /wifi` | 换网络，失败自动回落配网热点 |
| 主机名改名 | `POST /setname` | 改 mDNS 名（多板部署用） |
| 自动发现 | mDNS `_http._tcp.` + `/24` 兜底扫描 | 板子叫 `pixelclock-02` 就找 `pixelclock-02.local` |

---

## 📱 使用步骤

### 1. 编译 APK

```bash
# 需要 JDK 17 + Android SDK (compileSdk 34)
cd app-android
./gradlew assembleDebug
# 产物: app/build/outputs/apk/debug/app-debug.apk
```

### 2. 安装到手机

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

或把 APK 传到手机，用文件管理器点击安装（需允许「安装未知来源应用」）。

### 3. 连接板子

1. 手机和板子连**同一个 WiFi**
2. 打开 APP → 「控制台」→ 点「切换设备」→「自动发现」
3. 发现后点选即可连接

也可以手动填：
- IP 地址（如 `192.168.1.46`）
- **mDNS 主机名**（推荐，如 `pixelclock-02.local`）——板子换 IP 后不用重填

> 板子改过主机名的话，先用 IP 连上，在「设置」里查/改主机名。

---

## 🔒 网络安全说明

板子是局域网内明文 HTTP（ESP32 WebServer 没有 TLS）。APP 通过
`network_security_config.xml` 放行明文，公网 HTTPS 仍照常校验系统 CA。

> ⚠️ **一个容易踩的坑**：Android 的 `<domain>` 按**主机名/域名后缀**匹配，
> 它**不是 CIDR 网段**。写 `<domain>192.168.1.0</domain>` 不会匹配
> `192.168.1.46`；板子 IP 又由 DHCP 分配会变，无法穷举成 domain 列表。
> 所以局域网明文只能在 `base-config` 层放行。
>
> 写错的后果是系统直接拒绝请求：
> `java.io.IOException: Cleartext HTTP traffic to 192.168.1.46 not permitted`，
> APP 表现就是「连不上」，而且**日志里才有真因，界面上看不出**。

---

## 🩺 连不上怎么排查

APP 连接失败时会把**真实原因**显示出来，而不是笼统的"连接失败"。
打开「控制台」→「切换设备」，输入框下方会显示本机网络情况：

```
本机 192.168.1.7（板子应在 192.168.1.x 网段）
```

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 显示「本机未连接 WiFi」 | 手机用着移动数据 | 连上和板子同一个 WiFi |
| 本机与板子不同网段 | 板子 IP 变了 / 访客网络 | 手机连板子那个 WiFi |
| 连接超时 | 路由器 AP 隔离 | 关掉访客网络与 AP 隔离 |
| 自动发现扫不到 | 路由器屏蔽 mDNS 组播 | 手填 IP，功能完全一样 |

**最快的验证**：手机浏览器打开 `http://板子IP/status`。
能出 JSON 说明网络通，APP 也能用；打不开就是网络问题。

### mDNS 自动发现的两个前提

1. **必须持有 `WifiManager.MulticastLock`**。Android 会丢弃未持组播锁的进程
   收到的组播包，光申请 `CHANGE_WIFI_MULTICAST_STATE` 权限**没用**。
   不持锁时 `NsdManager` 永远收不到 `onServiceFound`。
2. 持有组播锁后仍被部分路由器过滤时，用 `LocalNet` 推出的**本机 /24 网段**
   做并发扫描兜底（1.2s 超时，只扫当前网段，不是全网扫描）。

---

## 📂 代码结构

```
app/src/main/java/com/ttqq/pixelclock/
  MainActivity.kt              入口
  net/
    BoardClient.kt             板子 HTTP 客户端（全部 REST 接口封装）
    BoardDiscovery.kt          mDNS 自动发现（持组播锁）+ /24 兜底扫描
    LocalNet.kt                本机 WiFi IP / 网段探测（连接诊断用）
    DialPreview.kt             base64 → RGB565 像素解码
  data/
    Prefs.kt                   本地偏好（板子地址 / 亮度 / 旋转）
  ui/
    PixelClockApp.kt           三个主页面 + 底部导航
    Components.kt              通用卡片 / 滑块 / 缩略图
    Dialogs.kt                 连接 / WiFi / 亮度预设 / 推送表盘
    MainViewModel.kt           状态中枢
    Theme.kt                   深色像素风主题
```

---

## ⚠️ 已知限制

- **Android 7.0+**（minSdk 24）
- mDNS 在部分路由器/机型上会被过滤 → APP 自动降级为 `/24` 网段扫描兜底
- 板子必须已连上 WiFi 且固件 ≥ v0.3.22（`/rotate`、`/status` 的 `rot` 字段）
- 蓝牙直连（BLE）**未启用**：固件 v0.3.18 起关闭了 BLE（BLE+WiFi 共存会耗尽堆导致 lwIP 枯竭），
  小程序侧的 BLE 通道同样处于关闭状态。要恢复需改固件 `ENABLE_BLE 1`，但会牺牲 WiFi 稳定性。

---

## 📄 许可

MIT
