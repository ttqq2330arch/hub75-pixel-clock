# HUB75 Pixel Clock 🕒

ESP32-S3 驱动的 **64×64 HUB75 全彩点阵像素时钟 / 氛围屏**开源固件。
板子自带网页控制台，支持表盘商店、亮度调节、屏幕旋转、WiFi 切换、动画播放，
开机自检 + 软启动供电保护，断网也能靠 NTP 缓存走时。

> HUB75 Pixel Clock — an open-source firmware for a 64×64 HUB75 RGB LED matrix
> clock driven by ESP32-S3, with a built-in web console (watch-face store,
> brightness, screen rotation, WiFi switching, animations).

---

## ✨ 特性

- **64×64 HUB75 全彩点阵**，双缓冲 DMA 驱动，刷新率约 120Hz
- **网页控制台**（`http://<板子IP>/`）：表盘商店 / 亮度滑块 / **屏幕旋转** / **WiFi 切换** / 动画
- **表盘商店**：内置多款表盘，可通过网页上传自定义 `.rgb565` 表盘
- **屏幕旋转**：0°/90°/180°/270° 一键切换，断电保存
- **WiFi 切换**：网页直接改 WiFi，连不上自动回落配网热点，永不失联
- **开机自检 + 供电软启动**：全屏自检亮度压到安全档，2.5s 亮度软爬坡，避免弱供电拉垮
- **NTP 时间同步**（CST-8），断网缓存走时
- **开源驱动参数**：矩阵初始化已对齐 WuyongLab-ESP32S3-PixelClock 同款已验证配置

| 项 | 值 |
|---|---|
| 主控 | ESP32-S3 **N16R8**（16MB Flash + 8MB PSRAM） |
| 屏 | P2.5 64×64 RGB HUB75 全彩点阵（5V/4A 额定，1/32 扫描） |
| 驱动库 | mrfaptastic/ESP32-HUB75-MatrixPanel-I2S-DMA |
| Flash 分区 | `partitions_16mb.csv`：OTA A/B + 表盘存储区 |
| 固件版本 | **v0.3.23** |

---

## ⚠️ 供电红线（先读再接线，不然烧板）

P2.5 全线密度高，全白实测可达 **4A 以上**。**严禁**从 ESP32 开发板 USB/VIN 取电给屏：

- 电源：独立 **5V/5A** 开关电源
- **供电走屏上的 VH4 插座（+5V/GND）**，排线只走信号
- 电源与屏 GND 必须和 ESP32 GND **共地**
- 屏 VCC/GND 入口并 **1000µF/25V 电解 + 0.1µF 陶瓷** 滤波

> 省钱提示：微雪 ESP32-S3-RGB-Matrix 驱动板（S3 + 排线座 + VH4 供电座三合一）可免飞线。

---

## 🔌 引脚映射（S3 专用，勿套老 ESP32 表）

N16R8 的 GPIO26~37 被 Flash + PSRAM 占用，GPIO19/20 是 USB。本映射已验证。

| HUB75 | GPIO | | HUB75 | GPIO |
|---|---|---|---|---|
| R1 | 4 | | CLK | 13 |
| G1 | 5 | | LAT | 11 |
| B1 | 6 | | OE | 12 |
| R2 | 7 | | A | 17 |
| G2 | 15 | | B | 18 |
| B2 | 16 | | C | 8 |
| | | | D | 9 |
| | | | **E** | **10** |

> E 脚（行扫描 16）**绝不能悬空**——64×64 是 1/32 扫描，缺 E 会上下半屏分裂。

可选外设：GPIO41/42 → SHT30 温湿度；GPIO14 → 蜂鸣器；GPIO0 → BOOT 键（短按切表盘 / 长按 3s 重置 WiFi）。

---

## 🛠️ 编译与烧录

需要 [PlatformIO](https://platformio.org/)（Core + ESP32 平台）：

```bash
cd hub75-pixel-clock
pio run                      # 编译
pio run -t upload            # 烧录（板子插 USB，必要时按住 BOOT 再插）
pio device monitor           # 115200 看启动日志
```

首次编译会自动拉取依赖（ESP32-HUB75-MatrixPanel-I2S-DMA 等）并下载工具链。
自定义板型定义在 `boards/esp32-s3-devkitc-1-n16r8.json`。

---

## 📡 首次配网

板子无 WiFi 凭据时开热点：

1. 手机/电脑连热点 **`PixelClock-Setup`**（密码 **`12345678`**）
2. 浏览器开 **`http://192.168.4.1`**
3. 填家里 WiFi 名称 + 密码 → 保存 → 板子重启连网
4. 开机横幅显示分配到的 IP（也可在路由器后台看设备名 `pixelclock`）

连上后随时访问 **`http://<板子IP>/`** 打开控制台。
> 换 WiFi 不必重刷：控制台「WiFi 切换」直接填，连不上会自动回落此热点。

---

## 🌐 网页控制台 & API 速查

| 功能 | 说明 |
|---|---|
| 表盘商店 | 切换/上传表盘 |
| 屏幕亮度 | 滑块 0–255，应用后保存 |
| **屏幕旋转** | 0°/90°/180°/270° 一键切换，断电保存 |
| **WiFi 切换** | 网页改 WiFi，自动回落热点 |

| 接口 | 方法 | 说明 |
|---|---|---|
| `/status` | GET | 返回 ip / rssi / host / bright / **rot** |
| `/brightness` | GET/POST | 读取/设置亮度（POST `?level=0..255`） |
| `/rotate` | GET/POST | 循环切换 / 指定角度（`?v=0..3`） |
| `/wifi` | GET/POST | 读取当前 SSID / 切换（`?ssid=&pass=`） |
| `/diallist` | GET | 已安装表盘清单 |
| `/faces` | GET | 内置表盘封面（gzip） |

---

## 📁 代码结构

```
src/
  main.cpp          主循环、任务调度、BOOT 键
  config.h          版本号、功能开关（ENABLE_BLE 等）、引脚/分辨率
  display_mgr.*     HUB75 初始化、自检、亮度软爬坡、旋转坐标变换
  net.cpp           网页服务器、配网门户、全部 REST 接口
  face_*.cpp        表盘（时钟/等离子/遥测/测试）与远程表盘播放
  faces_data.h      内置表盘封面数据
  push_page_gz.h    控制台网页（gzip，由 tools/gen_push_page_gz.py 生成）
  ble_service.*     BLE 服务（代码保留，config.h 默认关闭以省内存）
tools/
  gen_faces_web.py / gen_push_page_gz.py   网页→头文件生成
  flash_firmware.py                     一键烧录脚本
  cap_boot.py / cap_live.py             串口日志抓取
boards/
  esp32-s3-devkitc-1-n16r8.json        自定义板型
```

> 控制台网页改版流程：编辑 `tools/push_page_template.html` →
> `python tools/gen_push_page_gz.py` 重新生成 `src/push_page_gz.h` → 重新编译。

---

## 🙏 致谢

- 矩阵驱动：[mrfaptastic/ESP32-HUB75-MatrixPanel-I2S-DMA](https://github.com/mrfaptastic/ESP32-HUB75-MatrixPanel-I2S-DMA)
- 显示初始化参数参考：[WuyongLab/ESP32S3-PixelClock](https://github.com/WuyongLab/ESP32S3-PixelClock)
  （同硬件点亮验证，本固件驱动/时钟/blanking 参数已对齐其已验证配置）

## 📄 协议

[MIT](LICENSE) — 自由使用、修改、分发。
