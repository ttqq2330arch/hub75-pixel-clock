# -*- coding: utf-8 -*-
"""build_package.py — 把像素时钟项目打包成 0.03vx 交付包。

结构：
  像素时钟_v0.03vx/
  ├── 01_固件/        ← 单独列出：烧录产物 + 源码 + 烧录说明
  ├── 02_表盘库/      ← 58 个表盘 rgb565 + meta + 预览 + 清单
  ├── 03_文档/        ← 操作手册 / 库说明 / 项目 README / 版本说明
  └── 04_工具脚本/    ← 上传 / 烧录 / 监控 / 生成类维护脚本
输出：F:/桌面/0.03vx/像素时钟_v0.03vx.zip
"""
import json, csv, shutil, os, zipfile, io
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path("F:/AI数据/hub75-pixel-clock")
BUILD = Path("F:/hub75-build/esp32-s3")
DC = ROOT / "tools/dial_collection"
DIALS = DC / "dials"
OUT = DC / "out"
TARGET_DIR = Path("F:/桌面/0.03vx")
PKG_NAME = "像素时钟_v0.03vx"
STAGE = TARGET_DIR / "_stage" / PKG_NAME
ZIP_PATH = TARGET_DIR / (PKG_NAME + ".zip")

FG_NAME = {0: "白", 1: "黑", 2: "黄"}
MODE_NAME = {0: "经典HH:MM", 1: "方块数字"}

def clean():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

# ---------- 01 固件 ----------
def pack_firmware():
    d = STAGE / "01_固件"
    d.mkdir(parents=True)
    for b in ("firmware.bin", "bootloader.bin", "partitions.bin"):
        shutil.copy(BUILD / b, d / b)
    shutil.copy(ROOT / "platformio.ini", d)
    shutil.copy(ROOT / "partitions_16mb.csv", d)
    # 源码
    sd = d / "src"
    sd.mkdir()
    for f in sorted((ROOT / "src").iterdir()):
        if f.suffix in (".cpp", ".h"):
            shutil.copy(f, sd / f.name)
    # 烧录说明
    (d / "烧录说明.md").write_text(BURN_MD, encoding="utf-8")
    # 已有的构建/烧录文档
    if (ROOT / "docs/firmware-build-flash.md").exists():
        shutil.copy(ROOT / "docs/firmware-build-flash.md", d / "firmware-build-flash.md")

# ---------- 02 表盘库 ----------
def pack_dials():
    d = STAGE / "02_表盘库"
    (d / "dials").mkdir(parents=True)
    (d / "meta").mkdir(parents=True)
    stems = sorted(p.stem for p in DIALS.glob("*.rgb565"))
    rows = []
    for s in stems:
        shutil.copy(DIALS / (s + ".rgb565"), d / "dials" / (s + ".rgb565"))
        mp = OUT / s / "meta.json"
        if mp.exists():
            shutil.copy(mp, d / "meta" / (s + ".json"))
            m = json.loads(mp.read_text(encoding="utf-8"))
        else:
            m = {}
        rows.append({
            "序号": len(rows) + 1,
            "文件名": s,
            "标题": m.get("name", ""),
            "帧数": m.get("frames", ""),
            "帧率fps": m.get("fps", ""),
            "动画": "是" if m.get("animated") else "否",
            "叠加时钟": "是" if m.get("overlay") else "否",
            "叠加模式": MODE_NAME.get(m.get("ovmode", 0), ""),
            "字号": m.get("ovs", ""),
            "前景色": FG_NAME.get(m.get("ovfg", 0), ""),
            "位置ox": m.get("ox", ""),
            "位置oy": m.get("oy", ""),
        })
    # CSV
    with open(d / "表盘清单.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # 预览图
    for src, dst in [
        (DIALS / "_overview43.png", d / "预览-表盘总览.png"),
        (DC / "cwp-overlay-preview.png", d / "预览-时钟叠加落点.png"),
        (DC / "cwp-dials-clean.png", d / "预览-15个新表盘.png"),
    ]:
        if src.exists():
            shutil.copy(src, dst)
    # 额外生成一张 58 表盘总览（首帧拼图）
    build_overview(d / "预览-58表盘总览.png", stems)
    print(f"[表盘库] 共 {len(stems)} 个表盘已打包")

def build_overview(dst, stems):
    COLS = 8
    ROWS = (len(stems) + COLS - 1) // COLS
    CELL = 64 * 3
    sheet = Image.new("RGB", (COLS * CELL, ROWS * CELL), (24, 24, 28))
    for idx, s in enumerate(stems):
        raw = (DIALS / (s + ".rgb565")).read_bytes()
        im = Image.new("RGB", (64, 64)); px = im.load()
        for j in range(64 * 64):
            c = raw[j*2] | (raw[j*2+1] << 8)
            px[j % 64, j // 64] = (((c >> 11) & 0x1F) * 255 // 31,
                                   ((c >> 5) & 0x3F) * 255 // 63,
                                   (c & 0x1F) * 255 // 31)
        cx, cy = (idx % COLS) * CELL, (idx // COLS) * CELL
        sheet.paste(im.resize((CELL, CELL), Image.NEAREST), (cx, cy))
    sheet.save(dst)

# ---------- 03 文档 ----------
def pack_docs():
    d = STAGE / "03_文档"
    d.mkdir(parents=True)
    for src, dst in [
        (ROOT / "docs/操作手册.md", "操作手册.md"),
        (ROOT / "docs/dial-library.md", "dial-library.md"),
        (ROOT / "docs/多板部署.md", "多板部署.md"),
        (ROOT / "README.md", "README.md"),
    ]:
        if src.exists():
            shutil.copy(src, d / dst)
    (d / "版本说明.txt").write_text(VERSION_TXT, encoding="utf-8")

# ---------- 04 工具脚本 ----------
def pack_tools():
    d = STAGE / "04_工具脚本"
    d.mkdir(parents=True)
    tools = [
        "upload_dials.py", "flash_firmware.py", "serial_mon.py",
        "regen_cwp_dials.py", "regen_ult_digits.py", "gen_faces_web.py",
        "push_page_template.html", "test_push_page.js",
    ]
    for t in tools:
        p = ROOT / "tools" / t
        if p.exists():
            shutil.copy(p, d / t)
    # 附带 dial_collection 里的小工具
    for t in ["gif2frames.py"]:
        p = ROOT / "tools" / t
        if p.exists():
            shutil.copy(p, d / t)

# ---------- 压缩 ----------
def zipit():
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, PKG_NAME + "/" + str(p.relative_to(STAGE)))
    print(f"[ZIP] {ZIP_PATH}  ({ZIP_PATH.stat().st_size/1024/1024:.2f} MB)")

# ---------- 说明文本 ----------
BURN_MD = """# 固件烧录说明（v0.1.0 内部版本 / 交付包 0.03vx）

## 硬件
- 主控 ESP32-S3 **N16R8**（16MB Flash + 8MB PSRAM）
- 屏 P2.5 64×64 RGB HUB75 全彩点阵（160×160mm，5V/4A 额定，1/32 扫描）
- **红线**：屏必须独立 5V/5A 以上供电（走屏体 VH4 电源座），严禁从 ESP32 USB/VIN 取电；电源 GND 与 ESP32 GND 共地；屏入口并 1000µF 电解 + 0.1µF 陶瓷滤波。

## 烧录（Windows）
1. 安装 esptool（本包未带，可用 `pip install esptool`，或 PlatformIO 自带）。
2. 接好 USB（CH343 / ESP32-S3 原生 USB）。
3. 执行：`python flash_firmware.py`（自动找 CH343 串口；或 `python flash_firmware.py COM15` 指定端口）。
4. 烧录地址：
   - `0x00000` bootloader.bin
   - `0x08000` partitions.bin
   - `0x10000` firmware.bin
5. 波特率 921600；若 default_reset 失败，脚本会改用 no_reset（需手动按住 BOOT 再点 EN）。

## 首次启动
- 上电后连 WiFi（配网后存 NTP，时区 CST-8）。
- 表盘数据存在设备 LittleFS `/dials/`，**不烧进固件**；新增/更新表盘用 `upload_dials.py`，无需重刷。
- 默认开机自启上次表盘（flash 存储）。

## 源码
`src/` 为本包固件全部源码（C++）。如需自行构建，用 PlatformIO 打开工程根（含 platformio.ini）执行 `pio run`。
"""

VERSION_TXT = """像素时钟 交付包 0.03vx
================================
生成日期：2026-10-25
固件内部版本：v0.3.6（ESP32-S3 N16R8 + HUB75 64×64）
构建时间：2026-10-25（firmware.bin，v0.3.6）

v0.3.6 变更（修正 v0.3.5 缓冲位写反导致的全屏闪）
-------------------------------------------------
- 根因：v0.3.5 的 setBrightnessSafe8 把缓冲位写反了——`back_buffer_id` 本身就是「后台（未扫描）缓冲」，
  却写成了 `back_buffer_id ^ 1`（那其实是前台、正被 DMA 扫描的缓冲），再叠加 flip 导致整屏缓冲指针错乱 → 全屏乱闪。
- 修复：改回「始终只写 back_buffer_id 后台缓冲 → flip 让新亮度无撕裂上屏 → 补写新后台（=原前台，现已安全）」。
  两块最终都带新亮度，且 DMA 全程只扫带新亮度的缓冲 → 调亮度零闪烁（与 v0.3.5 设计意图一致，但缓冲位写对了）。
- 注：库的 stopDMAoutput() 内部会 resetbuffers() 清空帧缓冲，故不可用于运行时调亮度（会清屏），本版不采用。
- 网页「✓ 应用亮度」确认按钮 + 预设一键应用保留（拖动滑块只改数字、不实时下发）。
- 亮度仍写入 NVS 断电不丢；夜间 23:00–07:00 自动息屏压到 12（省电，白天恢复手动值）。

v0.3.5 变更（设计正确但实现写反缓冲位 → 全屏闪，已被 v0.3.6 取代）
-------------------------------------------------------------------
- 设计：写亮度时只写「未扫描的后台缓冲」→ 翻转让新亮度无撕裂上屏 → 再补写另一块。
- 缺陷：实现中把 back_buffer_id 与 back_buffer_id^1 搞反，实际写入了正在扫描的前台缓冲 → 全屏乱闪。仅作历史记录。

v0.3.4 变更（删爬升·单次直写，但未根除屏闪）
-----------------------------------------
- 删除 30ms 低通爬升，改为「目标亮度值变化时单次直写」。
- 经实测仍闪：根因是「单次直写也会撞上 DMA 扫描」而非「连写多次」，故 v0.3.5 改用后台缓冲安全写。

v0.3.3 变更（修亮度调节导致的屏闪）
-------------------------------
- 驱动层：Display::loop() 仅在亮度值真正变化时才调用 setBrightness8()，稳态不再每 30ms 重复写刷新寄存器，根除「拖动/调节时屏幕乱闪」。
- 网页：亮度改为「✓ 应用亮度」确认按钮 + 预设一键应用；拖动滑块只改数字、不再实时下发，避免拖动过程中屏闪。
- 亮度仍写入 NVS 断电不丢；夜间 23:00–07:00 自动息屏压到 12（省电，白天恢复手动值）。

v0.3.2 变更
-----------
- 网页新增「屏幕亮度」卡片：拖动滑块或点预设（暗15/中55/亮120/最亮200）即时调亮度。
- 新增后端接口：GET /brightness 读当前亮度、POST /brightness?level=N 设置并持久化（0–255）。
- /status 新增 bright 字段，便于核对当前亮度。
- 亮度写入 NVS，断电不丢；夜间 23:00–07:00 自动息屏压到 12（省电，白天恢复手动值）。

v0.3.1 变更
-----------
- 多板部署：主机名可配置。默认 pixelclock，可从 LittleFS /hostname.txt 覆盖；
  网页 POST /setname?name=pixelclock-02 直接改名并重启（用于多板互不抢名）。
- /status 新增 host 字段，便于核对每块板的名字。
- 烧录只刷 bootloader/partitions/firmware，不碰文件系统，表盘与名字配置均保留。

包含内容
--------
01_固件      —— 烧录产物（firmware/bootloader/partitions bin）+ 全部源码 + 烧录说明
02_表盘库    —— 58 个表盘（rgb565 帧数据 + meta 配置）+ 预览图 + 表盘清单.csv
03_文档      —— 操作手册 / 表盘库说明 / 多板部署 / 项目 README / 本版本说明
04_工具脚本  —— 上传 / 烧录 / 串口监控 / 表盘生成 等维护脚本

表盘来源
--------
- jnthas clockwise / mariobros-clock / clock-club / cw-cf-*（MIT）
- atctwo/clock25、vandalon/ultimatrix、vandalon/clockwizer
- ClockWise Plus（topyuan.top，15 个新表盘，2026-10-24 接入）
- 角色 IP（马里奥/宝可梦/星战/柯比/拉布布等）为厂商版权，**仅限个人把玩，禁止商用再分发**。

实时时钟
--------
每个表盘叠加一层 NTP 实时时钟（经典 HH:MM 或 方块数字两种风格），
可通过手机推送页（http://<设备IP>/）点表盘右上角 ⚙ 实时调整位置/字号/颜色。
浅色背景表盘已默认设为黑字（ovfg=1）以保证可见。

固件单独说明
------------
「固件」在本包中**单独列在 01_固件/**，与表盘数据（02_表盘库）、文档（03_文档）、
工具（04_工具脚本）物理隔离，便于只换固件不碰表盘、或只换表盘不重刷固件。
"""

if __name__ == "__main__":
    clean()
    pack_firmware()
    pack_dials()
    pack_docs()
    pack_tools()
    zipit()
    print("[完成] 包根目录:", STAGE)
