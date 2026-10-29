#!/usr/bin/env python3
# mkface.py — 把图片/PNG/GIF 转换成表盘包
#   产物: frames.bin(RGB565 LE) + manifest.json + preview.json
# 用法:
#   pip install pillow
#   python mkface.py input.png --id cat_tea --name "猫咪喝茶" --fps 4 \
#       --out ../miniprogram/data/faces/cat_tea
# 说明:
#   - 多帧 GIF 会逐帧导出（每帧 64x64，NEAREST 缩放，保持像素感）
#   - bg_mode=transparent 时，纯黑 (#000000) 像素视为透明（贴合固件约定）
#   - 与 docs/watchface-format.md 的 manifest 字段保持一致
import argparse, json, os, struct

W = H = 64


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def load_frames(path):
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("需要 Pillow：pip install pillow")
    img = Image.open(path).convert("RGB")
    n = getattr(img, "n_frames", 1)
    out = []
    for i in range(n):
        img.seek(i)
        f = img.convert("RGB").resize((W, H), Image.NEAREST)
        px = f.load()
        buf = bytearray()
        prev = ["#000000"] * (W * H)
        for y in range(H):
            for x in range(W):
                r, g, b = px[x, y]
                buf += struct.pack("<H", rgb565(r, g, b))
                prev[y * W + x] = "#%02x%02x%02x" % (r, g, b)
        out.append((buf, prev))
    return out


def main():
    ap = argparse.ArgumentParser(description="图片/GIF -> 表盘包")
    ap.add_argument("input")
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--author", default="you")
    ap.add_argument("--fps", type=int, default=1)
    ap.add_argument("--bg", default="transparent", choices=["transparent", "opaque"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    frames = load_frames(a.input)
    os.makedirs(a.out, exist_ok=True)

    with open(os.path.join(a.out, "frames.bin"), "wb") as f:
        for buf, _ in frames:
            f.write(buf)

    manifest = {
        "id": a.id,
        "name": a.name or a.id,
        "author": a.author,
        "width": W,
        "height": H,
        "pixel_format": "RGB565",
        "bg_mode": a.bg,
        "frame_count": len(frames),
        "fps": a.fps,
        "loop": True,
        "duration_ms": len(frames) * 1000 // a.fps if a.fps else 0,
        "checksum": "crc32-placeholder",
        "min_fw": "0.2.0",
    }
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(os.path.join(a.out, "preview.json"), "w", encoding="utf-8") as f:
        json.dump(frames[0][1], f)

    print("生成的表盘包 -> %s (%d 帧)" % (os.path.normpath(a.out), len(frames)))


if __name__ == "__main__":
    main()
