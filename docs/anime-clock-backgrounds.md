# 动漫/游戏动画背景素材档案（时钟背景用）

> 检索日期：2026-10-23 ｜ 目的：为 64×64 HUB75 像素时钟寻找「马里奥或其他动漫风格的循环动画」做背景表盘  
> 面板规格：64×64 RGB565（8192 字节/帧），BLE/HTTP 推送，见 `docs/face-push-protocol.md`

---

## 0. 结论速览（优先级排序）

| 优先级 | 资源                                             | 授权                           | 理由                                  |
| --- | ---------------------------------------------- | ---------------------------- | ----------------------------------- |
| ⭐⭐⭐ | Animated Lofi Pixel Art Background（雨窗 lofi）    | **CC0**                      | 循环动画背景、氛围感强、免署名可商用——**已下载并推送为开机动画** |
| ⭐⭐⭐ | **Pixel Torch 火把**（2026-10-23 第二批）             | **CC0**                      | 黑底跳动火把 6 帧，中心构图，时钟叠顶部黑区             |
| ⭐⭐⭐ | **Clock Animation 时钟动画**（第二批）                  | **CC0**                      | 290×290 表盘 12 帧（指针转动），本身就是钟         |
| ⭐⭐⭐ | **90s Computer Loading 加载动画**（第二批）             | **CC0**                      | 128×128 绿底复古 PC 4 帧，Loading 字幕闪烁    |
| ⭐⭐  | **Animated Water 水面**（第二批）                     | **CC0**                      | 16×16 水面瓦片 4 帧，×4 放大铺满              |
| ⭐⭐  | **Animated Quicksand 流沙**（第二批）                 | **CC0**                      | 16×16 马里奥流沙 6 帧，×4 放大               |
| ⭐⭐⭐ | Clarice 待机动画（jaymeehuynh）                      | CC-BY 3.0                    | 原生 96×64、6 帧待机——**已转换验证**           |
| ⭐⭐⭐ | Free Trippy Animated Backgrounds（Earthbound 风） | 免费（看页面）                      | 动漫感强、本身就是动画背景                       |
| ⭐⭐⭐ | Repeating/Tileable Backgrounds v1.2+           | 宽松（个人/商用可用）                  | 含 5 个 GIF 动画背景，16-64px 原生小尺寸        |
| ⭐⭐  | Cute Platformer Sisters                        | OGA-BY 3.0（署名 Master484）     | 卡通马里奥风全套角色动画                        |
| ⭐⭐  | Game Boy Platformer Tileset & Character        | **CC0**                      | GameBoy 四色灰阶，天然适合单色面板               |
| ⭐   | Mari0（开源马里奥同人）                                 | 代码 MIT / 素材 **BY-NC-SA 3.0** | 任天堂 IP 衍生，**仅限个人使用**，不得商用/再分发       |
| ⭐   | SMC-released-sprites                           | 非商用免费 + 署名                   | 任天堂 IP 衍生，仅限个人使用                    |
| —   | SuperTux                                       | GPL                          | 无任天堂 IP 风险的开源马里奥平替                  |

**⚠️ 版权红线**：马里奥形象归任天堂所有。本时钟是个人 DIY 作品，个人使用无风险；  
但若把基于马里奥素材的表盘上传到小程序商店/公开发布，则有侵权风险——**公开发布时只用 CC0 素材**。

---

## 1. CC0 / 宽松授权（可放心用，含商用）

### 1.1 Animated Lofi Pixel Art Background（雨窗 lofi）⭐强烈推荐 · 已落地

- **作者**：jaymeehuynh ｜ **授权**：CC0 ｜ **大小**：6MB zip
- **地址**：<https://opengameart.org/node/194903>
- **内容**：320×180/帧 的雨天窗景循环动画（43 帧 @10fps：雨丝/闪电/烛光/壁炉多层动画；  
  PNG spritesheet + JSON 帧数据 + GIF 预览 + FullHD 序列帧）
- **适配 64×64**：4K GIF 中心裁切 + NEAREST 缩放到 64×64，43 帧全量保留（PSRAM 放得下）
- **落地状态**：✅ 已转 43 帧推送板子 + 存 flash，**开机自动播放 + 实时时钟叠加**

### 1.2 第二批 CC0 动画批次（2026-10-23 下载，已全部转换待推送）

> 存放目录：`tools/cc0_batch/` ｜ 全部 OpenGameArt CC0（公有领域，免署名可商用）  
> 用户要求：「再下载一批 CC0 动画，不要雨窗的」→ 以下 5 个均已转成 64×64 RGB565，**设备在线后一条命令即可推送**

| 动画                 | OGA 源                                                                                              | 原始规格                    | 转换参数            | 产物                             | 观感                    |
| ------------------ | -------------------------------------------------------------------------------------------------- | ----------------------- | --------------- | ------------------------------ | --------------------- |
| **火把 torch**       | [animated-pixel-torch](https://opengameart.org/content/animated-pixel-torch)                       | 320×320 GIF 6 帧 @100ms  | `--fps 10` 中心裁  | `torch_frames.rgb565` 48KB     | 黑底跳动火把，时钟叠顶部黑区，氛围最佳   |
| **时钟动画 clockanim** | [clock-animation](https://opengameart.org/content/clock-animation)                                 | 290×290 GIF 12 帧 @100ms | `--fps 10` 中心裁  | `clockanim_frames.rgb565` 96KB | 紫盘指针转动，数字时钟叠加双钟效果     |
| **加载动画 loading**   | [90s-computer-loading-amination](https://opengameart.org/content/90s-computer-loading-amination)   | 128×128 GIF 4 帧 @100ms  | `--fps 10` 中心裁  | `loading_frames.rgb565` 32KB   | 绿底复古 PC，屏幕 Loading 闪烁 |
| **水面 water**       | [animated-water-platformer-16x16](https://opengameart.org/content/animated-water-platformer-16x16) | 16×16 GIF 4 帧 @400ms    | `--fps 2` ×4 放大 | `water_frames.rgb565` 32KB     | 海浪瓦片铺满，顶部浪花起伏         |
| **流沙 quicksand**   | [animated-quicksand-16x16](https://opengameart.org/content/animated-quicksand-16x16)               | 16×16 GIF 6 帧 @400ms    | `--fps 2` ×4 放大 | `quicksand_frames.rgb565` 48KB | 马里奥流沙陷阱，颗粒缓慢翻滚        |

**推送命令**（设备在线时，任选其一）：

```
cd tools/cc0_batch
python ../anim_push.py torch_frames.rgb565 --fps 10            # 播放（掉电丢）
python ../anim_push.py torch_frames.rgb565 --fps 10 --save     # 播放并存 flash 开机自动播
python ../anim_push.py --load                                   # 播 flash 存档
python ../anim_push.py --list                                   # 查当前动画状态
```

**存档备用（未转换）**：

- `gb_character.zip` — Game Boy Platformer Character（CC0，Chloe Wolfe）：16×16 角色 Idle/Walk/Roll/Jump/Fall 动画条
- `warped_city.zip` — Warped City（CC0，4.2MB 完整 demo）：`warped_props/` 已提取 7 个动画道具 GIF  
  （霓虹横幅 19×48×4、监控人脸 21×18×4、炮塔 25×23×6、无人机 55×52×4、角色 idle/walk/run 71×67）
- `Pixel_Torch.zip` / `clock_animation.zip` — 上述两个包的完整原版（含 SVG 源文件、Aseprite 源文件）

### 1.3 Game Boy Platformer Tileset & Character

- **作者**：Chad Wolfe ｜ **授权**：CC0（公有领域）｜ **下载**：3327 次
- **地址**：<https://opengameart.org/content/game-boy-platformer-tileset-character>
- **内容**：GameBoy 风格 tileset + 带动画的角色（走/跳等）
- **适配**：四色灰阶 → RGB565 直接映射；适合做「单色/低饱和度」背景层

### 1.4 itch.io 免费素材大户（按创作者收藏）

| 创作者                     | 代表包                                  | 授权              | 备注                                              |
| ----------------------- | ------------------------------------ | --------------- | ----------------------------------------------- |
| Pixel Frog              | Pixel Adventure 1/2                  | CC0             | 20FPS 动画 spritesheet                            |
| Ansimuz                 | SunnyLand                            | CC0             | 完整平台包 + 视差背景                                    |
| 0x72                    | DungeonTileset II                    | CC0             | 16×16 含火把动画                                     |
| Cainos                  | Pixel Art Top Down Basic             | 自有条款（免费用/禁倒卖）   | 32×32                                           |
| edermunizz              | **Free Trippy Animated Backgrounds** | 免费（看页面）         | Earthborn 风动画背景，含 Godot 版                       |
| Feony Labs              | Animated Pixel-Art Backgrounds       | 免费              | 纯动画背景包                                          |
| Screaming Brain Studios | Seamless Space Backgrounds FREE 64   | 免费              | 64 张无缝太空背景                                      |
| FagelTomten             | Repeating/Tileable Backgrounds v1.2+ | 宽松（个人/商用可用、禁转载） | 75 个 16-64px 可平铺背景，**含 5 个 GIF 动画背景**，免费样品 10 个 |

---

## 2. 马里奥 / 平台游戏风（任天堂 IP 衍生——仅限个人使用）

### 2.1 Mari0（马里奥 + 传送门）⭐素材最全

- **地址**：<https://github.com/Stabyourself/mari0> （镜像 github.org/calebhearth/mari0）
- **授权**：**代码 MIT，素材 BY-NC-SA 3.0**（非商用、相同方式共享、署名）
- **素材位置**：`graphics/` 目录——mario.png（含跑/跳/蹲/游泳全套动画）、goomba.lua、koopa.lua、coinblockanimation.lua、fireball.lua、firework.lua、castlefire.lua 等
- **用法**：`graphics/mario.png` 是 spritesheet，逐帧切出即可得到 16×16 马里奥动画
- **⚠️**：任天堂 IP 衍生 + NC 条款 → 只能个人把玩，不得商用/公开再分发

### 2.2 SMC-released-sprites（Super Mario Construct 官方公开素材）

- **地址**：<https://github.com/Level-Share-Square/SMC-released-sprites>
- **授权**：非商用免费、必须署名、不得直接转载（项目内间接使用可以）
- **内容**：SMAS/SMW/Mobile 各版本马里奥系 spritesheet，数量极大

### 2.3 KaykyOne/mario（JS 网页版马里奥）

- **地址**：<https://github.com/KaykyOne/mario> ｜ **授权**：MIT
- **内容**：`images/mario.gif`、`mario-parado.png`、`mario-pulando.png`、管道/云朵
- 注意：素材是任天堂形象复刻，MIT 是仓库作者的单方面声明，仍受任天堂 IP 约束 → 个人使用

### 2.4 Mario Bros Art（OpenGameArt 的"致敬版"马里奥素材）

- **地址**：<https://opengameart.org/content/mario-bros-art>
- **作者**：Oroku Karai ｜ 内容：为 knock-off 版超级玛丽收集的美术（含 Hero's Field 等合集）
- 授权见各子素材页，需逐一核对

### 2.5 SuperTux（开源平替，零 IP 风险）

- **地址**：<https://github.com/SuperTux/supertux> ｜ **授权**：GPL
- 内容：完整开源平台游戏（Tux 为主角），data/images 下有大量动画 spritesheet
- 适合想要"马里奥玩法感但版权干净"的场景

---

## 3. 其他动漫风资源

| 资源                                    | 地址                                               | 授权         | 说明                                                            |
| ------------------------------------- | ------------------------------------------------ | ---------- | ------------------------------------------------------------- |
| Animated Lofi Pixel Art Background    | opengameart.org/node/194903                      | CC0        | 雨天窗景循环——**已落地为开机动画**                                          |
| Clarice, the Noctural Creature Hunter | opengameart.org/node/178478                      | CC-BY 3.0  | 96×64 原生角色动画（idle/run/attack/hurt），同作者还有 Kael 等——**Idle 已转换** |
| Free Trippy Animated Backgrounds      | edermunizz.itch.io                               | 免费         | Earthbound 风                                                  |
| Cute Platformer Sisters               | opengameart.org/content/cute-platformer-sisters  | OGA-BY 3.0 | 卡通姐妹全套动画（受 Giana Sisters/Rod Land/马里奥启发）                      |
| animated quicksand 16x16              | opengameart.org/content/animated-quicksand-16x16 | CC0        | 16×16 6 帧流沙动画，含 GIF + strip                                   |
| Cute Platformer Sisters 附带            | 同上                                               | OGA-BY     | 64×64 角色头像、金币/烟尘特效动画                                          |
| Pixel Planet Generator                | itch.io                                          | 看页面        | 程序化像素星球                                                       |
| Unknown Nights 壁纸包                    | itch.io                                          | 看页面        | 星空生物像素壁纸                                                      |
| Lofi Cities（浏览器生成）                    | worldprogramming.org                             | 看页面        | 480×270 像素城市夜景 4 分钟无缝循环（东京/巴黎/香港…）                            |

**工具**：Piskel（开源像素动画编辑器，piskelapp.com / github.com/piskelapp/piskel）——  
可以自己画 64×64 的循环动画，导出 GIF 或 PNG 序列，正好喂给下面的转换工具。

---

## 4. 转换工具链（本项目自带，已真机验证）

### 4.1 动画时钟固件能力（2026-10-23 上线）

- **多帧动画缓冲**：PSRAM 512KB，最多 **64 帧 × 8192B**（43 帧雨窗实测无压力）
- **实时时钟叠加**：`HH:MM`（5×7 字体 ×2，黑色描边任意背景可读）+ 底部秒进度条
- **flash 持久化**：动画存 `/anim.bin`（LittleFS，10MB 分区），**重启自动播放**
- **HTTP 接口**（`http://192.168.1.50`，同一 WiFi）：
  | 接口                                 | 方法   | 说明                             |
  | ---------------------------------- | ---- | ------------------------------ |
  | `/pushface?off=N&len=M`            | POST | 分块 hex 写入（off 可跨帧，N=帧×8192+偏移） |
  | `/anim?frames=N&fps=F&overlay=0/1` | POST | 启动动画播放并切 REMOTE 面              |
  | `/animsave`                        | POST | 当前动画存 flash（重启自动播）             |
  | `/animload`                        | POST | 播放 flash 里的动画                  |
  | `/animlist`                        | GET  | 动画状态 JSON                      |
- **网页推送器**：`http://192.168.1.50/` 新增「动画背景」区块——播放/存储/上传 .rgb565 动画（帧数=文件大小/8192），手机浏览器直接换动画

### 4.2 GIF/序列帧 → 64×64 动画帧

```
F:/AI数据/hub75-pixel-clock/tools/gif2frames.py
```

- 输入：GIF 文件或 PNG 序列帧目录
- 处理：中心裁切（`--fit` 改 Letterbox）→ NEAREST 缩放到 64×64 → RGB565 小端 → 抽帧
- 输出：`<name>_frames.json` + `<name>_frames.rgb565`（8192×帧数 字节）
- **动画模式**：`--anim 192.168.1.50 --fps 10 --save`  
  （整帧写入板子动画缓冲 → `/anim` 启动 → `/animsave` 存 flash，一步到位）
- 旧播放模式 `--play` 保留（逐帧 commit，适合单帧验证）

### 4.3 已落地演示（全部真机验证通过）

| 演示               | 素材                                      | 授权                | 状态                |
| ---------------- | --------------------------------------- | ----------------- | ----------------- |
| **雨窗 lofi 动画时钟** | jaymeehuynh CC0 雨窗（43 帧 @10fps + 时钟叠加）  | CC0               | ✅ 已存 flash，开机自动播放 |
| **Clarice 待机动画** | jaymeehuynh Clarice Idle（6 帧，bbox 裁切放大） | CC-BY 3.0         | ✅ 已验证播放           |
| 马里奥跑勤            | Mari0 素材（8 帧 SMB 场景）                    | BY-NC-SA + 任天堂 IP | ✅ 已验证（仅个人）        |

- `tools/make_clarice_anim.py` — Clarice Idle spritesheet（576×64=6×96×64）按 alpha bbox  
  裁出角色本体再放大到 44px 高（整帧缩放角色只剩 22×25 会太小，这是实测踩坑点）
- `tools/anim_push.py` — 通用 .rgb565 动画推送：`python anim_push.py x.rgb565 --fps 10 --save`；  
  `--load` 播放 flash 存档；`--list` 查状态

### 4.4 表盘 → 面板（其它链路）

- BLE：小程序表盘商店（M3 协议，单帧）
- 新静态表盘注册：json 放进 `miniprogram/data/faces/<name>/preview.json` + 更新 `faces-index.json` + 重跑 `gen_faces_web.py`

### 4.5 帧率与体积经验值

| 帧数   | 每帧字节 | 一轮循环  | 推送耗时(HTTP) |
| ---- | ---- | ----- | ---------- |
| 6 帧  | 8192 | 48KB  | ~5s        |
| 16 帧 | 8192 | 128KB | ~12s       |
| 43 帧 | 8192 | 344KB | ~32s       |

面板 ICN2037 刷新 90Hz，动画帧间隔建议 **100-200ms**（5-10fps 观感最像复古游戏）。  
推送用 1024 字节/片的 hex 分块（WebServer 会把含 `\0` 的二进制 body 按 C 串截断，必须 hex）。

---

## 5. 下一步方向

1. **✅ 已下载更多 CC0 动画背景**（2026-10-23，见 §1.2）：火把/时钟动画/90s加载/水面/流沙 5 个已转待推；  
   Warped City 完整包 + GB 角色包已存档。**剩余待挖**：edermunizz Free Trippy Animated Backgrounds（itch.io 免费包）、  
   Lofi Cities（worldprogramming.org，480×270 城市夜景 4 分钟循环，浏览器生成——可考虑抓帧）；  
   FagelTom
2. ten 的 5 个 GIF 动画背景在付费包（$1.96）里，免费样品只有静态背景，暂未购买
3. **时钟叠加位置可配置**：目前固定底部居中，letterbox 素材（64×36）上下黑边正好放时钟
4. **多个动画切换**：flash 存多个 `/anim_<name>.bin`，网页/按钮循环切换
5. 马里奥素材（Mari0）继续仅个人把玩，不进公开渠道
6. Warped City 动画道具（`tools/cc0_batch/warped_props/`）可合成「赛博城市夜景」背景：  
   静态楼体做底 + 霓虹横幅/监控人脸/无人机叠加成多帧动画（仿 make_mario_demo.py 做法）
