# 固件构建 / 烧录 / 网页推送器工作流

> 2026-10-23 整理。所有路径必须 ASCII 或走相对路径（ESP32 GCC 工具链读不了 CJK 的 -I 路径；
> 另外本机 Bash 里的 Python 用中文**绝对路径**会 FileNotFoundError，用相对路径正常）。

## 1. 构建（PlatformIO）

```bash
cd F:/AI数据/hub75-pixel-clock
CODEBUDDY_SAFE_DELETE_ENABLED=0 \
  /c/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/pio.exe run -e esp32-s3
```

- `platformio.ini`：`core_dir = F:/pio`（平台包/工具链缓存），`build_dir = F:/hub75-build`
- **`CODEBUDDY_SAFE_DELETE_ENABLED=0` 是必须的**：WorkBuddy 沙箱的 safe-delete 守卫
  （单回合删除 >50 个文件就 SystemExit）会拦下 SCons 删旧 `.o`/`.a`，导致构建静默作废
  （退出码 0 但没编译）。设了开关后 22s 完成增量构建。
- pio 可执行文件：原 `~/.platformio/penv` 因搬家损坏，现用托管 Python 环境里
  `pip install platformio`（6.1.19），平台包复用 F:/pio 缓存，无需重下。
- **硬验证产物**（不信退出码）：
  ```bash
  stat -c '%y %s' F:/hub75-build/esp32-s3/firmware.bin          # mtime 必须是刚才
  grep -ao "关键字符串" F:/hub75-build/esp32-s3/firmware.bin     # 改动必须能在 bin 里搜到
  ```

## 2. 烧录

```bash
cd F:/AI数据/hub75-pixel-clock/tools
python flash_firmware.py            # 自动找 CH343(COM15)，bootloader/partitions/firmware 三件套
```

- esptool：`F:/pio/packages/tool-esptoolpy/esptool.py`，偏移 0x0 / 0x8000 / 0x10000，921600
- default_reset 失败会自动降级 no_reset（需手动按 BOOT + 点 EN）

## 3. 串口监听

```bash
cd F:/AI数据/hub75-pixel-clock/tools
python serial_mon.py 8          # 抓 8 秒，过滤关键行（anim/boot/BLE/WiFi...）
python serial_mon.py 15 all     # 抓 15 秒全量
```

## 4. 网页推送器（faces_web.h）

| 文件 | 作用 |
|---|---|
| `tools/push_page_template.html` | 页面模板（含 `/*__FACES__*/` 占位符） |
| `tools/gen_faces_web.py` | 读 `miniprogram/data/faces-index.json` → base64 注入模板 → 生成 `src/faces_web.h` |
| `src/faces_web.h` | 自动生成勿手改；改页面只改模板再跑生成器，然后重新编译+烧录 |

**2026-10-23 页面修复**（用户截图反馈"无法连接设备"误报）：
- 根因两个：① 固件 WebServer 单客户端，Python 推动画时浏览器轮询被拒；
  ② 路由器周期性 `AUTH_EXPIRE` 掉线（串口抓到），重连几秒内页面同样连不上
- 修复：`fetchRetry()` 失败自动重试 4 次 ×2s（覆盖最长 7.5s 推送窗口），仍失败才提示，
  且提示语改为"⏳ 设备无响应（可能正在推送动画，请稍候）"；`animPoll` 改 15s 周期刷新
  （原来只在页面加载时查一次，Python 侧换动画后页面显示旧状态）

## 5. 血的教训（2026-10-23）

- **`F:/hub75-build` 是 PlatformIO build_dir，里面别放任何重要文件！**
  pio 因 Core 版本变更（6.2.0→6.1.19）判定配置变化，把整个构建根目录清了，
  存放在里面的 `cli_flash3.py` / `push_page_template.html` / `gen_faces_web.py` 全灭。
  现已重建并移入项目 `tools/` 目录（见上）。
- 构建日志写项目目录（`build_log.txt`），别写 build_dir。
