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

板子是局域网内明文 HTTP。APP 通过 `network_security_config.xml` **只对私有网段放行明文**，公网仍强制 HTTPS：

```
192.168.x.x / 10.x.x.x / 172.16.x.x / *.local  →  允许明文
其它所有域名                                      →  只允许 HTTPS
```

---

## 📂 代码结构

```
app/src/main/java/com/ttqq/pixelclock/
  MainActivity.kt              入口
  net/
    BoardClient.kt             板子 HTTP 客户端（全部 REST 接口封装）
    BoardDiscovery.kt          mDNS 自动发现 + /24 兜底扫描
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
