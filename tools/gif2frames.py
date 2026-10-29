#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gif2frames.py — GIF / PNG 序列帧 → 64x64 像素时钟表盘帧数据

用法：
  # 转换（生成 json + 二进制）
  python gif2frames.py input.gif
  python gif2frames.py frames_dir/            # PNG 序列目录
  python gif2frames.py input.gif -o rain --max-frames 12 --fps 8

  # 转换后直接循环播放到面板（HTTP 逐帧推送，无需改固件）
  python gif2frames.py input.gif --play 192.168.1.50 --max-frames 12 --fps 8

输出：
  <out>_frames.json    {"name":..,"w":64,"h":64,"fps":n,"frames":[["#RRGGBB"x4096],..]}
  <out>_frames.rgb565  原始二进制，8192 x 帧数 字节（与 /pushface 帧格式一致）

注意：
  - 像素图缩放必须用 NEAREST，否则会糊
  - 默认从中心裁正方形，适合"方形构图"素材；--fit 模式改为 Letterbox 补边
"""
import argparse
import json
import os
import struct
import sys
import time
import urllib.request

W, H = 64, 64
FRAME_BYTES = W * H * 2


def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def frame_to_rgb565_bytes(img):
    """PIL RGB 64x64 -> 小端 RGB565 字节串 + 4096 个 #RRGGBB"""
    img = img.convert("RGB")
    px = img.load()
    raw = bytearray(FRAME_BYTES)
    hexes = []
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            c = rgb565(r, g, b)
            raw[y * W * 2 + x * 2] = c & 0xFF
            raw[y * W * 2 + x * 2 + 1] = c >> 8
            # 还原成 8bit 色（RGB565 量化后的值，保证板子上看到的和 json 一致）
            r8 = (c >> 11) << 3
            g8 = ((c >> 5) & 0x3F) << 2
            b8 = (c & 0x1F) << 3
            hexes.append("#%02X%02X%02X" % (r8, g8, b8))
    return bytes(raw), hexes


def center_crop_square(img):
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    return img.crop((left, top, left + s, top + s))


def letterbox_square(img):
    w, h = img.size
    s = max(w, h)
    out = Image.new("RGB", (s, s), (0, 0, 0))
    out.paste(img.convert("RGB"), ((s - w) // 2, (s - h) // 2))
    return out


def load_gif(path, max_frames):
    from PIL import Image, ImageSequence
    im = Image.open(path)
    frames = []
    for fr in ImageSequence.Iterator(im):
        frames.append(fr.copy())
    return frames


def load_png_dir(path, max_frames):
    from PIL import Image
    files = sorted(f for f in os.listdir(path)
                   if f.lower().endswith((".png", ".bmp", ".jpg", ".jpeg")))
    return [Image.open(os.path.join(path, f)) for f in files]


def decimate(frames, max_frames):
    n = len(frames)
    if n <= max_frames:
        return frames
    idx = [round(i * (n - 1) / (max_frames - 1)) for i in range(max_frames)]
    return [frames[i] for i in idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="GIF 文件或 PNG 序列目录")
    ap.add_argument("-o", "--out", default=None, help="输出文件名前缀（默认取输入名）")
    ap.add_argument("--max-frames", type=int, default=12, help="最多保留帧数（默认 12）")
    ap.add_argument("--fps", type=float, default=8.0, help="播放帧率（默认 8）")
    ap.add_argument("--fit", action="store_true", help="Letterbox 补边而非中心裁切")
    ap.add_argument("--play", metavar="IP", default=None,
                    help="转换后直接循环 HTTP 推送到面板（如 192.168.1.50）")
    ap.add_argument("--once", action="store_true", help="配合 --play：只播一轮")
    ap.add_argument("--anim", metavar="IP", default=None,
                    help="动画背景模式：整帧写入板子动画缓冲并启动播放（固件侧循环）")
    ap.add_argument("--no-overlay", action="store_true",
                    help="配合 --anim：不叠加实时时钟")
    ap.add_argument("--save", action="store_true",
                    help="配合 --anim：同时存进 flash，重启自动播放")
    args = ap.parse_args()

    from PIL import Image

    name = args.out or os.path.splitext(os.path.basename(args.input.rstrip("/\\")))[0]
    name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    # ---- 读入 ----
    if os.path.isdir(args.input):
        frames = load_png_dir(args.input, args.max_frames)
    else:
        frames = load_gif(args.input, args.max_frames)
    if not frames:
        print("[ERR] no frames loaded from", args.input)
        return 2
    total = len(frames)
    frames = decimate(frames, args.max_frames)
    print("[LOAD] %d frames (decimated to %d, max=%d)" % (total, len(frames), args.max_frames))

    # ---- 逐帧处理 ----
    out_frames = []
    raw_all = bytearray()
    for i, fr in enumerate(frames):
        im = letterbox_square(fr) if args.fit else center_crop_square(fr)
        im = im.resize((W, H), Image.NEAREST)
        raw, hexes = frame_to_rgb565_bytes(im)
        raw_all += raw
        out_frames.append(hexes)
        if i == 0 or i == len(frames) - 1:
            print("[FRAME %2d] px(0,0)=%s nonzero=%d/%d" % (
                i, hexes[0], sum(1 for h in hexes if h != "#000000"), len(hexes)))

    # ---- 落盘 ----
    json_path = name + "_frames.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"name": name, "w": W, "h": H,
                   "fps": args.fps, "frames": out_frames}, f, separators=(",", ":"))
    bin_path = name + "_frames.rgb565"
    with open(bin_path, "wb") as f:
        f.write(raw_all)
    print("[SAVE] %s (%.1f KB) + %s (%d bytes = %d frames x %d)" % (
        json_path, os.path.getsize(json_path) / 1024,
        bin_path, len(raw_all), len(frames), FRAME_BYTES))

    # ---- 动画背景模式：整帧写入板子动画缓冲 ----
    if args.anim:
        ip = args.anim
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def post(path, data=b""):
            req = urllib.request.Request("http://%s%s" % (ip, path), data=data, method="POST")
            req.add_header("Content-Type", "application/octet-stream")
            try:
                with opener.open(req, timeout=15) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")
            except Exception as e:
                return -1, str(e)

        n = len(frames)
        print("[ANIM] pushing %d frames to http://%s (anim buffer)" % (n, ip))
        for i in range(n):
            fr = bytes(raw_all[i * FRAME_BYTES:(i + 1) * FRAME_BYTES])
            off = 0
            while off < FRAME_BYTES:
                ln = min(1024, FRAME_BYTES - off)
                st, body = post("/pushface?off=%d&len=%d" % (i * FRAME_BYTES + off, ln),
                                fr[off:off + ln].hex().encode())
                if st != 200:
                    print("[ANIM] frame %d chunk off=%d FAIL -> %s %s" % (i, off, st, body))
                    return 2
                off += ln
            if i % 4 == 0 or i == n - 1:
                print("[ANIM] frame %d/%d pushed" % (i + 1, n))
        ov = 0 if args.no_overlay else 1
        st, body = post("/anim?frames=%d&fps=%d&overlay=%d" % (n, int(args.fps), ov))
        print("[ANIM] /anim ->", st, body)
        if st != 200:
            return 2
        if args.save:
            st, body = post("/animsave")
            print("[ANIM] /animsave ->", st, body)
        return 0

    # ---- 播放 ----
    if args.play:
        ip = args.play
        interval = 1.0 / args.fps
        # 直连，绕开系统代理（否则 502）
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def post(path, data=b""):
            req = urllib.request.Request("http://%s%s" % (ip, path), data=data, method="POST")
            req.add_header("Content-Type", "application/octet-stream")
            try:
                with opener.open(req, timeout=10) as r:
                    return r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode("utf-8", "replace")
            except Exception as e:
                return -1, str(e)

        def push_frame(fr_bytes):
            # 分块 hex（规避 WebServer 对含 \0 二进制 body 的截断）+ commit
            off = 0
            while off < len(fr_bytes):
                ln = min(512, len(fr_bytes) - off)
                st, body = post("/pushface?off=%d&len=%d" % (off, ln),
                                fr_bytes[off:off + ln].hex().encode())
                if st != 200:
                    return False, "chunk off=%d -> %s %s" % (off, st, body)
                off += ln
            st, body = post("/pushface?commit=1", b"")
            return st == 200, body

        print("[PLAY] pushing %d frames to http://%s/pushface at %.1ffps (Ctrl+C stop)" % (
            len(frames), ip, args.fps))
        n = 0
        try:
            while True:
                t0 = time.time()
                for i in range(len(frames)):
                    fr_bytes = bytes(raw_all[i * FRAME_BYTES:(i + 1) * FRAME_BYTES])
                    ok, msg = push_frame(fr_bytes)
                    if not ok:
                        print("[PLAY] frame %d FAIL: %s" % (i, msg))
                    n += 1
                    # 补偿推送耗时，保持帧率
                    delay = interval - (time.time() - t0 - i * interval)
                    if delay > 0:
                        time.sleep(delay)
                if args.once:
                    break
        except KeyboardInterrupt:
            pass
        print("[PLAY] stopped after %d frames" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
