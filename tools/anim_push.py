#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anim_push.py — 把 .rgb565 动画帧文件推送到板子动画缓冲并启动播放

用法：
  python anim_push.py clarice_frames.rgb565 --ip 192.168.1.50 --fps 8 --overlay 0
  python anim_push.py rain_frames.rgb565   --ip 192.168.1.50 --fps 10 --overlay 1 --save
  python anim_push.py --load --ip 192.168.1.50        # 播放 flash 里存的动画
  python anim_push.py --list --ip 192.168.1.50        # 查动画状态
"""
import argparse
import sys
import time
import urllib.request
import urllib.error

FRAME_BYTES = 8192
CHUNK = 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help=".rgb565 帧文件（帧数 = 大小/8192）")
    ap.add_argument("--ip", default="192.168.1.50")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--overlay", type=int, default=1, help="1=叠加实时时钟 0=纯动画")
    ap.add_argument("--save", action="store_true", help="存 flash，重启自动播放")
    ap.add_argument("--burst", action="store_true",
                    help="整分钟触发模式：帧 0..N-2 为爆发序列，最后一帧待机（mario-coin 用）")
    ap.add_argument("--load", action="store_true", help="播放 flash 里存的动画")
    ap.add_argument("--list", action="store_true", help="查询动画状态 JSON")
    args = ap.parse_args()

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def post(path, data=b""):
        req = urllib.request.Request("http://%s%s" % (args.ip, path),
                                     data=data, method="POST")
        req.add_header("Content-Type", "application/octet-stream")
        try:
            with opener.open(req, timeout=15) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            return -1, str(e)

    def get(path):
        try:
            with opener.open("http://%s%s" % (args.ip, path), timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            return -1, str(e)

    if args.list:
        st, body = get("/animlist")
        print("[LIST]", st, body)
        return 0 if st == 200 else 2

    if args.load:
        st, body = post("/animload")
        print("[LOAD]", st, body)
        return 0 if st == 200 else 2

    if not args.file:
        print("[ERR] need .rgb565 file (or --load / --list)")
        return 2

    data = open(args.file, "rb").read()
    if len(data) % FRAME_BYTES != 0:
        print("[ERR] file size %d not multiple of %d" % (len(data), FRAME_BYTES))
        return 2
    n = len(data) // FRAME_BYTES
    print("[PUSH] %s: %d frames @ %dfps overlay=%d" % (args.file, n, args.fps, args.overlay))
    t0 = time.time()
    for i in range(n):
        fr = data[i * FRAME_BYTES:(i + 1) * FRAME_BYTES]
        off = 0
        while off < FRAME_BYTES:
            ln = min(CHUNK, FRAME_BYTES - off)
            st, body = post("/pushface?off=%d&len=%d" % (i * FRAME_BYTES + off, ln),
                            fr[off:off + ln].hex().encode())
            if st != 200:
                print("[PUSH] frame %d off=%d FAIL -> %s %s" % (i, off, st, body))
                return 2
            off += ln
        print("[PUSH] frame %d/%d ok" % (i + 1, n))
    st, body = post("/anim?frames=%d&fps=%d&overlay=%d%s"
                    % (n, args.fps, args.overlay, "&burst=1" if args.burst else ""))
    print("[ANIM]", st, body)
    if st != 200:
        return 2
    if args.save:
        st, body = post("/animsave")
        print("[SAVE]", st, body)
        if st != 200:
            return 2
    print("[DONE] %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
