#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_clarice_anim.py — Clarice 待机动画 → 64x64 动画背景帧数据

素材：clarice/Clarice-noctural-creature-hunter-96x64-[Standard]/SpriteSheets/
      Clarice-noctural-creature-hunter-Idle.png  (576x64 = 6 帧 x 96x64)
授权：CC-BY 3.0 (jaymeehuynh, opengameart.org/node/178478) — 署名即可用

输出：clarice_frames.rgb565（6 x 8192 字节）+ clarice_frames.json
用法：配合 gif2frames 的二进制直接推，或 python gif2frames.py 的 --anim 流程
      （本脚本只负责切帧缩放，推送用 tools/anim_push.py）
"""
import json
import os
import sys

W, H = 64, 64
FRAME_BYTES = W * H * 2
SHEET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "clarice", "Clarice-noctural-creature-hunter-96x64-[Standard]",
                     "SpriteSheets", "Clarice-noctural-creature-hunter-Idle.png")
N_FRAMES = 6
CHAR_H = 44          # 角色在面板上的高度（顶部留白给观感，底部避开时钟叠加区）


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def main():
    from PIL import Image
    im = Image.open(SHEET).convert("RGBA")
    fw = im.size[0] // N_FRAMES          # 96
    ch = im.size[1]                     # 64
    raw_all = bytearray()
    out_frames = []
    for i in range(N_FRAMES):
        fr = im.crop((i * fw, 0, (i + 1) * fw, ch))
        # 按 alpha bbox 裁出角色本体（原帧 96x64 里角色只占 ~22x25，直接缩整帧会太小）
        bbox = fr.split()[3].getbbox()
        if bbox:
            fr = fr.crop(bbox)
        cw, chh = fr.size
        # 等比放大到 CHAR_H 高（NEAREST 保像素硬边）
        nw = max(1, round(cw * CHAR_H / chh))
        fr = fr.resize((nw, CHAR_H), Image.NEAREST)
        if nw > W:                       # 超宽则按宽裁
            fr = fr.crop(((nw - W) // 2, 0, (nw - W) // 2 + W, CHAR_H))
            nw = W
        # 黑底画布，水平居中，垂直靠上（y=2，底部留给时钟叠加区）
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas.paste(fr, ((W - nw) // 2, 2), fr)
        px = canvas.load()
        for y in range(H):
            for x in range(W):
                r, g, b = px[x, y]
                c = rgb565(r, g, b)
                raw_all.append(c & 0xFF)
                raw_all.append(c >> 8)
        out_frames.append(["#%02X%02X%02X" % (
            ((rgb565(*px[x, y]) >> 11) << 3),
            (((rgb565(*px[x, y]) >> 5) & 0x3F) << 2),
            ((rgb565(*px, y) if False else rgb565(*px[x, y]) & 0x1F) << 3))
            for y in range(H) for x in range(W)])
        nz = sum(1 for k in range(0, FRAME_BYTES, 2)
                 if raw_all[i * FRAME_BYTES + k] or raw_all[i * FRAME_BYTES + k + 1])
        print("[FRAME %d] nonzero=%d/%d" % (i, nz, W * H))

    with open("clarice_frames.rgb565", "wb") as f:
        f.write(raw_all)
    with open("clarice_frames.json", "w", encoding="utf-8") as f:
        json.dump({"name": "clarice", "w": W, "h": H, "fps": 8,
                   "frames": out_frames}, f, separators=(",", ":"))
    print("[SAVE] clarice_frames.rgb565 (%d bytes) + clarice_frames.json" % len(raw_all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
