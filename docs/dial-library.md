# 表盘斗图库（58 个）— 来源、架构与维护手册

> 2026-10-24 建成。设备：ESP32-S3 N16R8 + HUB75 64×64。
> 手机操作：`http://192.168.1.50/`（或 `pixelclock.local`）→ 下滑到「表盘斗图库」→ 点缩略图即上屏。

## 1. 架构：表盘库在设备 FS，不在固件里

| 组件 | 位置 | 说明 |
|---|---|---|
| 表盘数据 | 设备 LittleFS `/dials/<stem>.rgb565` | 58 个共 ~7.3MB（spiffs 分区 ~10MB） |
| 表盘元数据 | `/dials/<stem>.json` | 一行文本：`fps overlay burst ovmode ox oy ox2 ovs ovfg`（9 字段，sscanf 按字段数兼容旧文件） |
| 固件页面 | `src/faces_web.h` | 只 81KB；gallery 动态加载，不再嵌表盘 |

**为什么改 FS 架构**：表盘 base64 嵌进固件时，19 个表盘就占了 950KB（app 分区仅 2MB，固件已 1.85MB）；
43 个表盘 4.2MB 根本放不下。FS 方案后固件回落到 ~900KB，表盘数量无上限（加表盘不用重编固件）。

### HTTP 接口（net.cpp）

| 接口 | 方法 | 用途 |
|---|---|---|
| `/dialup?name=&off=&len=&fps=&overlay=&burst=&final=1` | POST | 分片上传（hex body，2048B/片）；`final=1` 写 meta 收尾，可带 `play=1`；叠加层参数 `ovmode=&ox=&oy=&ox2=&ovs=&ovfg=` |
| `/diallist` | GET | `{"dials":[{"n","c","f","o","b","s","m","x","y","x2","sc","fg"}...]}`（c=帧数 f=fps o=叠加 b=burst s=字节 m=叠加模式 x/y/x2=位置 sc=字号 fg=前景色 0白/1黑/2黄） |
| `/dialpreview?name=` | GET | 首帧 8192B 的 base64（页面 canvas 画缩略图） |
| `/dialplay?name=` | POST | 从 FS 载入并播放（fps/overlay/burst/叠加位置全读 meta） |
| `/dialov?name=&mode=&ox=&oy=&ox2=&ovs=&ovfg=[&ov=]` | POST | **实时调整已存表盘的叠加层**（只传要改的字段；该表盘正在播放则下一帧生效，meta 同步落盘） |
| `/setname?name=<host>` | POST | **多板部署**：把主机名写入 LittleFS `/hostname.txt` 并重启。`name` 限 `a-z 0-9 -`、长度 1..31，如 `pixelclock-02`。重启后 mDNS 名变为 `http://pixelclock-02.local/` |
| `/status` | GET | `{"ip","rssi","host","push"}`（`host`=当前主机名，默认 `pixelclock`） |

**叠加时钟两种模式**（drawOverlayClock，face_remote.cpp）：
- **mode 0 经典**：白字黑描边 `HH:MM` + 底部黄色秒进度条。`ox=-1` 水平居中，`oy` 文本左上角 y，`ovs` 字号 1..2。
- **mode 1 方块数字**（ult-mario/ult-luigi）：两位块内 7×7 马里奥字体画实时 HH/MM，
  先把数字带（块内 x+1..x+17, y+6..y+12）填成块体色盖掉旧数字再画。`ox/oy`=小时块左上角，
  `ox2`=分钟块左上角（块 19×19，默认 12,11 / 34,11，与 vandalon/ultimatrix 的 PNG 一致）。
  排版算法（墨点居中 + pitch 8/9 补偿）移植自 ultimatrix Clockface.cpp（PolyForm Noncommercial，个人使用）。
- 推送页面每个表盘格子右上角 ⚙ 齿轮 → 调整对话框：点画面直接定位、方向键微调、模式/字号切换、
  7×7 字形实时预览，保存走 `/dialov`。
- `/anim.bin`（PAN1）头 0.3.x 起扩到 16B，新增 `mode ox oy ox2 scale`；旧 8B 头文件仍兼容（读默认值）。

**踩坑记录**：
- **Content-Type 必须 `application/octet-stream`**：urllib 默认加 `x-www-form-urlencoded`，WebServer 会把 body
  当表单解析，固件 `arg("plain")` 收到空串（上传全变 0 字节）。
- **大缓冲必须 static**：loop 任务栈只有 8KB，`uint8_t buf[8192]` 放栈上 → 栈溢出 → 看门狗重启
  （症状：调 /dialpreview 后设备重启、动画变回 /anim.bin 里的旧表盘）。
- **页面缩略图要限并发**：43 个并发 preview 请求会把单客户端 WebServer 挤爆（20/43 卡死），
  页面改为 3 个一批的队列。

## 2. 表盘清单（58 个）

### 来自 jnthas/Clockwise-XE1E（同硬件项目，16 个）
donkey-kong、snoopy3、christmassnoopy(28帧)、goomba_move、nyan-cat、pac-man、star-wars、Star_Wars_v2、
clock-club、retro-computer、nigth-clock-1、eletrogate、pepsi-final-2、coca-cola-1、Hora_en_Palabras-2、prueba-1

### 来自 jnthas/mariobros-clock（3 个）
mario-scene（静态）、mario-jump（2帧跳一下）、**mario-coin（10帧 burst：每分钟整点跳顶金币）**

### 来自 jnthas/clock-club 社区主题（2 个）
space-invaders（太空侵略者）、umbrella-corporation（生化危机保护伞）

### 来自 atctwo/clock25 的 64×64 GIF（10 个动画）
amogus、bowser、katamari、kirby、squid、suavemente、puppycat、n64、cat-bobbing、dipp

### 来自 vandalon/ultimatrix 的 64×64 渲染图（9 个静态）
ult-mario、ult-luigi、ult-pacman、ult-tetris、ult-home（叠时钟）；
ult-f1、ult-football、ult-word、ult-motogp（自带内容，默认不叠）
（ult-mario/ult-luigi 已重生成：擦掉 PNG 里烘焙的 "14 39" 死数字，meta 标记
`ovmode=1` 方块时钟，面板上两个问号块显示 NTP 实时 HH:MM，位置可经页面 ⚙ 调整）

### 来自 jnthas cw-cf 官方表盘（3 个）
castlevania（恶魔城钟楼整图）、pokedex（图图 + 精灵）、world-map（世界地图 + 红色时区线）

### 来自 ClockWise Plus（topyuan.top/clock，15 个）— 2026-10-24 新增
transformer、mc-torch、coffee、pikachu、sharpei、girl、labubu、hello-kitty、twinkle、
zootopia、mc-village、codex、gta6、zelda、particle

**来源与提取**：ClockWise Plus（Felix Feng @yuan910715）固件**闭源**，27 个表盘是编译进固件的
代码（1-27 编号），设备配置页从 `http://topyuan.top/clock/en4.3.js` 远程加载。唯一可用素材是
`clock_press` 说明仓库里的 27 个 **64×64 预览 GIF**（512×512 = 8 倍最近邻放大，8×8 块纯色，
`Image.BOX` 降采样零误差）。
- 去重：01-09 / 13 / 17 已有源版跳过；24_rainy_window（雨窗）用户明确不要 → 保留 15 个新的。
- 27 个预览都烘焙了演示时间 "17:30"（部分含秒组 "00"），需**擦除 + 叠加实时时钟**。
- 转换脚本 `regen_cwp_dials.py`，逐表盘配 `bbox`（烘焙时间闭区间）、`anchor`、叠加位置/字号/前景色。

**擦除方案（`erase_time`，从简单到内容感知）**：
1. 默认 **anchor 3×3 中位色平面填充**（适合纯色/静态背景，9 个表盘用）。
2. `fill="right"`：**右侧行-wise 采样 + 跨帧众数**——transformer 的天空是垂直渐变
   （G 通道 y0=166→y20=146），单一平面填充会出现色斑；改为每行取 bbox 右侧干净带该行主色填充。
   动画中机器人头部会穿过左侧采样带（frame1/19），故用「跨帧众数」——2 帧污染抵不过 19 帧天空。
3. bbox 必须**逐表盘精确测量**数字真实范围（非估计）：hello-kitty 粉色数字实到 x11-54（原 bbox
   x12-51 两侧残留）、codex 青色数字实到 x7-55 且 y43/y63 有设计边框线（bbox 过高会误伤边框）。

**浅底表盘用黑字**：pikachu / sharpei / labubu / zootopia 是浅色底，白字看不见 →
meta `ovfg=1`（0 白 / 1 黑 / 2 黄）。`upload_dials.py` 的 `dial_meta`/`upload_one` 已加 `ovfg` 传递。

## 3. 工具链（tools/dial_collection/）

| 脚本 | 用途 |
|---|---|
| `extract_cw_images.py` | Clockwise JSON 里的 base64 PNG → `imgs/<md5>.rgba` + manifest |
| `render_cw.js` | Node vm 沙箱跑 Clockwise 编辑器原版渲染器 → `out/<name>/frames.rgba` |
| `package_cw_dials.py` | `out/` → `dials/<name>.rgb565` + PNG 预览 + json |
| `extract_mb.py` | mariobros-clock 的 assets.h（RGB565 数组）→ 场景拼装 |
| `extract_src2.py` | 第二批：clock25 GIF / ultimatrix PNG / 恶魔城 / 图图 / 世界地图 |
| `regen_ult_digits.py` | ult-mario/luigi：擦 PNG 烘焙数字带（BAND=(1,6,17,7)）→ 写 ovmode=1 |
| `regen_cwp_dials.py` | ClockWise Plus 15 个预览 GIF → 擦烘焙时间 + 叠时钟 → rgb565/meta |
| `../upload_dials.py` | dials/*.rgb565 → 设备 FS（分片 + 重试 + 核对，含 ovfg 传递） |
| `test_push_page.js` | 页面 JS 的 Node vm-sandbox DOM-stub 测试（烧录前必过，8 项断言） |
| `../gen_faces_web.py` | 重新生成推送页（DIALS 已固定为空数组） |

**加新表盘流程**：提取/渲染 → `dials/<stem>.rgb565` → `python tools/upload_dials.py --only <stem>` → 刷新页面即见。
不用重编固件。

**渲染注意**：C 数组注释里的 `// 0x0010` 会被正则当像素值（多 256 个/行），必须先 `re.sub(r"//[^\n]*", "", txt)`。

## 4. 授权说明（全部开源，个人使用）

- jnthas 全家桶（clockwise / mariobros-clock / clock-club / cw-cf-*）：MIT
- atctwo/clock25、vandalon/ultimatrix、vandalon/clockwizer：见各仓库 LICENSE
- **ClockWise Plus（topyuan.top）**：固件闭源；15 个表盘取自其**公开预览 GIF**，仅个人把玩、**禁止商用/再分发**
- 角色 IP（马里奥/吃豆人/星战/柯比/宝可梦/ among us / 皮卡丘 / Hello Kitty / 疯狂动物城 等）为厂商 IP，**仅限个人把玩，不得商用**
