# -*- coding: utf-8 -*-
"""gen_faces_web.py — 生成 src/faces_web.h（网页版表盘推送器，PROGMEM）

数据源：miniprogram/data/faces-index.json（6 个表盘，各 4096 个 #RRGGBB）
转换：#RRGGBB → RGB565 小端（与小程序 render.js toRGB565 / 固件 blit 逐位一致）
      → base64 → 嵌入 push_page_template.html 的 /*__FACES__*/ 占位符
输出：src/faces_web.h（const char PUSH_PAGE[] PROGMEM = R"PWGL(...)PWGL"）

用法：python gen_faces_web.py

2026-10-23 重建说明：原脚本在 F:/hub75-build/（PlatformIO build_dir），
被 pio 因 Core 版本变更清构建目录时误删。模板与脚本现已移入项目 tools/ 目录，
不再与构建产物混放。注意：R"PWGL(" raw string 里不能出现 )PWGL" 序列。

2026-10-24 新增：注入 16 个像素时钟表盘（tools/dial_collection/dials/*.rgb565）
到 /*__DIALS__*/ 占位符 —— 页面「表盘斗图库」区块，点缩略图一键上屏。
fps 取自 out/<name>/meta.json（Clockwise 原始值），Hora_en_Palabras 自带
文字时间故 overlay=0，其余默认叠实时时钟。
"""
import base64
import gzip
import io
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent      # F:/AI数据/hub75-pixel-clock
TPL = ROOT / "tools" / "push_page_template.html"
OUT = ROOT / "src" / "faces_web.h"

HEADER = """// ============================================================
// faces_web.h — 自动生成，勿手改！
// 由 tools/gen_faces_web.py 生成：
//   源数据 miniprogram/data/faces-index.json（6 表盘 x 4096 px）
//   格式 RGB565 小端 base64（与固件 face_remote blit 逐位一致）
//   STA 模式由 net.cpp 在 GET / 提供（网页版表盘推送器）
// ============================================================
#pragma once
#include <Arduino.h>

"""


def face_to_b64(preview):
    assert len(preview) == 4096, f"expect 4096 px, got {len(preview)}"
    buf = bytearray(8192)
    for i, hexs in enumerate(preview):
        r = int(hexs[1:3], 16)
        g = int(hexs[3:5], 16)
        b = int(hexs[5:7], 16)
        c = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        buf[i * 2] = c & 0xFF
        buf[i * 2 + 1] = (c >> 8) & 0xFF
    return base64.b64encode(bytes(buf)).decode("ascii")


DIAL_DIR = ROOT / "tools" / "dial_collection" / "dials"
META_DIR = ROOT / "tools" / "dial_collection" / "out"


def make_thumb(frame: bytes) -> str:
    """首帧 RGB565 → 48x48 PNG(base64)，做网格缩略图。"""
    from PIL import Image
    img = Image.new("RGB", (64, 64))
    px = img.load()
    for i in range(4096):
        c = frame[i * 2] | (frame[i * 2 + 1] << 8)
        r = ((c >> 11) & 0x1F) * 255 // 31
        g = ((c >> 5) & 0x3F) * 255 // 63
        b = (c & 0x1F) * 255 // 31
        px[i % 64, i // 64] = (r, g, b)
    img = img.resize((48, 48), Image.NEAREST)
    bio = io.BytesIO()
    img.save(bio, "PNG", optimize=True)
    return base64.b64encode(bio.getvalue()).decode("ascii")


def collect_dials():
    dials = []
    for f in sorted(DIAL_DIR.glob("*.rgb565")):
        stem = f.stem
        raw = f.read_bytes()
        assert len(raw) % 8192 == 0, f"{stem}: {len(raw)} 不是 8192 倍数"
        frames = len(raw) // 8192
        fps, name, overlay = 6, stem, 1
        meta_p = META_DIR / stem / "meta.json"
        if meta_p.exists():
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            name = m.get("name", stem)
            fps = int(m.get("fps", 6)) or 6
        if stem.startswith("Hora"):
            overlay = 0          # 文字时钟自带时间显示，不再叠加数字钟
        fps = max(1, min(30, fps))
        dials.append({
            "n": name, "t": make_thumb(raw[:8192]),
            "d": base64.b64encode(raw).decode("ascii"),
            "c": frames, "f": fps, "o": overlay,
            "b": int(meta_p and json.loads(meta_p.read_text(encoding="utf-8")).get("burst", 0)) if meta_p.exists() else 0,
        })
        print(f"  dial {stem:22s} {frames:>2d}帧 @{fps}fps ov={overlay}")
    return dials


def write_faces_data_h(faces):
    """把 FACES 全量（含预览 d）gzip 后写成 src/faces_data.h（PROGMEM），
    供设备的 /faces 端点按需下发。首页不再内嵌 FACES，从而精简到 <5KB，
    在 BLE+MIN_MODEM（被迫开 modem-sleep）下也能稳定加载；FACES 预览由前端
    fetch('/faces') 带重试拉取，掉一两次自动重来，不影响主控制面板。"""
    OUT2 = ROOT / "src" / "faces_data.h"
    raw = json.dumps(faces, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = gzip.compress(raw, compresslevel=9)
    lines = [
        '// faces_data.h - auto-generated, DO NOT EDIT!',
        '// 表盘商店(FACES)全量含预览，gzip -9 后由 /faces 端点按需下发',
        '// regen:  python tools/gen_faces_web.py',
        '#pragma once',
        '#include <Arduino.h>',
        '',
        'static const uint8_t FACE_DICT_GZ[] PROGMEM = {',
    ]
    row = []
    for b in gz:
        row.append('0x%02X,' % b)
        if len(row) == 16:
            lines.append('  ' + ''.join(row))
            row = []
    if row:
        lines.append('  ' + ''.join(row))
    lines.append('};')
    lines.append('static const size_t FACE_DICT_GZ_LEN = %d;' % len(gz))
    OUT2.write_text('\n'.join(lines), encoding="utf-8")
    print(f"  faces_data.h  raw {len(raw)} -> gz {len(gz)} bytes")


def main():
    idx = json.loads((ROOT / "miniprogram" / "data" / "faces-index.json").read_text(encoding="utf-8"))
    faces = []
    for f in idx["faces"]:
        faces.append({"n": f["name"], "id": f["id"], "d": face_to_b64(f["preview"])})
        print(f"  face {f['id']:8s} {f['name']:6s} -> {len(faces[-1]['d'])} b64 chars")

    # FACES 全量（含预览 d）写入 faces_data.h，由 /faces 端点下发；首页不再内嵌。
    write_faces_data_h(faces)

    # 首页 PUSH_PAGE 的 FACES/DIALS 都留空：表盘商店预览改由前端 fetch('/faces')
    # 按需拉取（带重试），表盘库改走设备 LittleFS（/diallist+/dialpreview+/dialplay）。
    # 这样首页体积从 ~13KB 降到 <5KB，BLE+MIN_MODEM 被迫开 modem-sleep 时也能稳定加载。
    # 注意模板里是 "var FACES = /*__FACES__*/;"（占位符前不能留 []），这里替换为 "[]"。
    fjs = "[]"
    djs = "[]"
    tpl = TPL.read_text(encoding="utf-8")
    assert "/*__FACES__*/" in tpl, "模板缺少 /*__FACES__*/ 占位符"
    assert "/*__DIALS__*/" in tpl, "模板缺少 /*__DIALS__*/ 占位符"
    assert ")PWGL\"" not in tpl, "模板含 )PWGL\" 会截断 raw string"
    html = tpl.replace("/*__FACES__*/", fjs).replace("/*__DIALS__*/", djs)
    OUT.write_text(HEADER + 'const char PUSH_PAGE[] PROGMEM = R"PWGL(\n' + html + '\n)PWGL";\n',
                   encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
