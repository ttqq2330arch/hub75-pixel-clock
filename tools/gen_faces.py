#!/usr/bin/env python3
# gen_faces.py — 生成表盘静态数据（零依赖，纯标准库）
# 产物：
#   data/faces-index.json        小程序直接 require 的表盘清单（含 64x64 预览像素）
#   data/faces/<id>/manifest.json  后期上 COS/GitHub 时的单表盘元数据
#   data/faces/<id>/preview.json   单表盘预览像素（与 frames.bin 同源，M3 推送用）
#
# 注：真实表盘由 tools/mkface.py 从图片/GIF 转换；本脚本仅生成内置演示表盘。
import json, math, os, random

W = H = 64
BLACK = "#000000"
OUT = os.path.join(os.path.dirname(__file__), "..", "miniprogram", "data")


def blank():
    return [BLACK] * (W * H)


def make_smiley():
    px = blank()
    for y in range(H):
        for x in range(W):
            if (x - 32) ** 2 + (y - 32) ** 2 <= 28 ** 2:
                px[y * W + x] = "#ffd400"
            if (x - 23) ** 2 + (y - 26) ** 2 <= 5 ** 2 or (x - 41) ** 2 + (y - 26) ** 2 <= 5 ** 2:
                px[y * W + x] = "#1a1a1a"
            if 20 <= x <= 44 and 40 <= y <= 48:
                if ((x - 32) ** 2 + (y - 40) ** 2 <= 14 ** 2) and not ((x - 32) ** 2 + (y - 40) ** 2 <= 9 ** 2):
                    px[y * W + x] = "#1a1a1a"
    return px


def make_heart():
    px = blank()
    for y in range(H):
        for x in range(W):
            nx, ny = (x - 32) / 16.0, (y - 32) / 16.0
            if (nx * nx + ny * ny - 1) ** 3 - nx * nx * ny * ny * ny <= 0:
                px[y * W + x] = "#ff2d55"
    return px


def make_star():
    px = blank()
    for y in range(H):
        for x in range(W):
            ang = math.atan2(y - 32, x - 32) + math.pi / 2
            r = math.hypot(x - 32, y - 32)
            star_r = 28 * (0.55 + 0.45 * abs(math.cos(2.5 * ang)))
            if r <= star_r:
                px[y * W + x] = "#ffd400"
    return px


def make_rainbow():
    px = blank()
    bands = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#007aff", "#5856d6", "#af52de"]
    for y in range(H):
        for x in range(W):
            px[y * W + x] = bands[(x * len(bands)) // W]
    return px


def make_matrix():
    px = blank()
    random.seed(42)
    for y in range(H):
        for x in range(W):
            if random.random() < 0.16:
                shade = random.randint(70, 255)
                px[y * W + x] = "#%02x%02x%02x" % (0, shade, 0)
    return px


def make_fire():
    px = blank()
    for y in range(H):
        for x in range(W):
            t = y / W
            half = 4 + 18 * t
            if abs(x - 32) <= half and y > 6:
                c = "#ff3b30" if t < 0.4 else ("#ff9500" if t < 0.7 else "#ffcc00")
                px[y * W + x] = c
    return px


FACES = [
    ("smiley", "笑脸", "内置", "表情", make_smiley),
    ("heart", "爱心", "内置", "表情", make_heart),
    ("star", "星星", "内置", "装饰", make_star),
    ("rainbow", "彩虹", "内置", "装饰", make_rainbow),
    ("matrix", "数字雨", "内置", "动效", make_matrix),
    ("fire", "火焰", "内置", "动效", make_fire),
]


def main():
    faces = []
    for fid, name, author, cat, fn in FACES:
        preview = fn()
        faces.append({
            "id": fid, "name": name, "author": author, "category": cat,
            "width": W, "height": H, "fps": 1, "bg_mode": "transparent",
            "preview": preview,
        })
        d = os.path.join(OUT, "faces", fid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"id": fid, "name": name, "author": author, "width": W,
                       "height": H, "pixel_format": "RGB565", "bg_mode": "transparent",
                       "frame_count": 1, "fps": 1}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(d, "preview.json"), "w", encoding="utf-8") as f:
            json.dump(preview, f)

    idx = {"version": 1, "faces": faces}
    with open(os.path.join(OUT, "faces-index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    print("generated %d faces -> %s" % (len(faces), os.path.normpath(OUT)))


if __name__ == "__main__":
    main()
