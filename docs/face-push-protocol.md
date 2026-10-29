# 表盘推送帧协议（M3）

小程序「表盘商店 → 推送到设备」走的就是这套协议。
固件实现：`src/ble_service.cpp`（DataCb）+ `src/face_remote.cpp`（帧缓冲/渲染）。
小程序实现：`miniprogram/utils/ble.js`（pushFace）+ `miniprogram/utils/render.js`（toRGB565）。

## 1. 载体

BLE 服务 `4f8c0000-1f0a-4c1e-9b2d-000000000001`，特征：

| 特征 | UUID 后缀 | 属性 | 方向 | 用途 |
|---|---|---|---|---|
| TIME | …0002 | write | App→设备 | uint32 LE 秒，校时 |
| TIME_R | …0003 | read | App←设备 | uint32 LE 秒，读时间 |
| FACE | …0004 | write | App→设备 | uint8，切换表盘索引 |
| DATA | …0005 | write / write-no-response | App→设备 | 表盘帧数据流（本协议） |
| STATUS | …0006 | read + notify | App←设备 | uint8，推送状态码 |

## 2. 帧格式

- 尺寸固定 64×64，**RGB565 小端**（低字节在前），共 **8192 字节**。
- 像素排列：行优先，第 0 字节 = (x0,y0) 低字节。
- 转换公式：`(r>>3)<<11 | (g>>2)<<5 | (b>>3)`，透明像素（小程序 `#000000`）直接送 0x0000，面板不亮。

## 3. DATA 特征包格式

每个写包 = 1 字节命令 + 参数：

| 命令 | 格式 | 说明 |
|---|---|---|
| `0x01` 数据块 | `[01][off_lo][off_hi][len][payload...]` | off=16bit 偏移，len=1~200；`off=0` 的一包表示新帧开始 |
| `0x02` 提交 | `[02][crc_lo][crc_hi]` | 全帧 CRC16 校验，通过才生效 |
| `0x03` 中止 | `[03]` | 放弃当前传输 |

分包大小自适应 MTU：MTU≥200 用 200 字节/包（约 42 包），iOS(185) 用 160，兜底 16。
小程序每包之间间隔 12ms，防 BLE 拥塞丢包。

## 4. STATUS 状态码（notify）

| 值 | 含义 | 小程序行为 |
|---|---|---|
| 0 | 空闲 | — |
| 1 | 接收中 | 显示进度 |
| 2 | 提交成功，已切到 REMOTE 表盘 | 提示完成 |
| 3 | CRC 校验失败 | 提示重试（传输损坏） |
| 4 | 中止 / 接收超时（3s 无新包） | 提示重试 |

固件在状态变化时立即 notify；小程序提交后等 STATUS 通知确认（8s 超时）。

## 5. 完整时序

```
App                              设备
 |-- setBLEMTU(247) ------------->|
 |-- notify(STATUS, on) --------->|
 |-- [01][00 00][C8][200B] ------>|  beginRx()，status=1
 |-- [01][C8 00][C8][200B] ------>|  ...
 |        （共约 42 包）            |
 |-- [02][crc_lo][crc_hi] ------->|  CRC 校验
 |                                |-- 通过：gValid=true, status=2
 |                                |-- 自动切换到 Faces 索引 3（REMOTE）
 |<-- notify STATUS = 2 ----------|
```

## 6. 固件侧要点

- 帧缓冲 `RemoteFace::gBuf[8192]` 在 DRAM 静态区（不用 PSRAM，DMA 每帧读，DRAM 更快）。
- 越界包、长度不符的包直接拒绝并中止整帧传输。
- `commit` 的 CRC 用 `RemoteFace::crc16()`：CRC-16/XMODEM（poly 0x1021，init 0x0000），与小程序 `crc16()` 逐位一致（测试向量 "123456789" → 0x31C3）。
- 远程表盘在注册表索引 3（`config.h: FACE_IDX_REMOTE`）；没收到过表盘时显示 "PUSH FACE / FROM APP" 占位。
- 物理按键短按一样能切到索引 3 看占位/已推内容。

## 7. 兼容性

- STATUS 特征是 v0.2.0 固件新增。连旧固件时 `pushFace` 会在 `_enableStatusNotify` 阶段报「设备无 STATUS 特征（固件版本过旧，请升级到 v0.2.0+）」，不会静默失败。
- DATA 特征同时开了 write 和 write-no-response：小程序走 write（有回执），桌面工具可走 NR 提速。
