#!/usr/bin/env python3
# upload_dials.py — 把 dial_collection/dials/*.rgb565 全部推到设备 LittleFS /dials/
# 用法：python upload_dials.py [--ip 192.168.1.50] [--only stem1,stem2] [--force]
# 元数据来自 dial_collection/out/<stem>/meta.json（fps/overlay/burst）
import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DIALS = HERE / "dial_collection" / "dials"
OUT = HERE / "dial_collection" / "out"
CHUNK = 2048          # 固件单分片上限 4096B，留一半余量
RETRY = 4             # 单分片重试次数（路由器周期性踢线窗口）


def post(url, data=b"", timeout=30):
    # 必须显式 octet-stream：urllib 默认会加 x-www-form-urlencoded，
    # WebServer 会把 body 当表单参数解析，导致固件 arg("plain") 收到空串
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def dial_meta(stem):
    m = {}
    p = OUT / stem / "meta.json"
    if p.exists():
        m = json.loads(p.read_text(encoding="utf-8"))
    fps = int(m.get("fps", 6) or 6)
    fps = max(1, min(30, fps))
    overlay = int(m.get("overlay", 0 if stem.startswith("Hora") else 1))
    burst = int(m.get("burst", 0))
    # 叠加层参数（0.3.x：经典/方块模式 + 位置，ult-mario/ult-luigi 用方块模式）
    ovmode = int(m.get("ovmode", 0))
    ox = int(m.get("ox", -1))
    oy = int(m.get("oy", 46))
    ox2 = int(m.get("ox2", 34))
    ovs = int(m.get("ovs", 2))
    ovfg = int(m.get("ovfg", 0))
    return fps, overlay, burst, ovmode, ox, oy, ox2, ovs, ovfg


def post_retry(url, data=b""):
    last = None
    for i in range(RETRY):
        try:
            return post(url, data)
        except Exception as e:                      # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def upload_one(ip, path, stem):
    raw = path.read_bytes()
    assert len(raw) % 8192 == 0, f"{stem}: {len(raw)} 不是 8192 倍数"
    frames = len(raw) // 8192
    fps, ov, bu, ovmode, ox, oy, ox2, ovs, ovfg = dial_meta(stem)
    nchunk = 0
    for off in range(0, len(raw), CHUNK):
        chunk = raw[off:off + CHUNK]
        final = off + CHUNK >= len(raw)
        q = (f"http://{ip}/dialup?name={stem}&off={off}&len={len(chunk)}"
             f"&fps={fps}&overlay={ov}&burst={bu}"
             f"&ovmode={ovmode}&ox={ox}&oy={oy}&ox2={ox2}&ovs={ovs}&ovfg={ovfg}"
             + ("&final=1" if final else ""))
        st, body = post_retry(q, chunk.hex().encode("ascii"))
        if st != 200:
            raise RuntimeError(f"{stem} off={off}: HTTP {st} {body}")
        nchunk += 1
    return frames, nchunk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default="192.168.1.50")
    ap.add_argument("--only", default="", help="逗号分隔的表盘 stem 过滤")
    ap.add_argument("--force", action="store_true", help="已存在的也重传")
    args = ap.parse_args()

    st, body = get(f"http://{args.ip}/status", timeout=8)
    if st != 200:
        print("设备不在线", file=sys.stderr)
        return 1

    have = set()
    st, body = get(f"http://{args.ip}/diallist", timeout=10)
    if st == 200:
        have = {d["n"] for d in json.loads(body).get("dials", [])}
    print(f"设备 FS 已有 {len(have)} 个表盘")

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    files = sorted(DIALS.glob("*.rgb565"))
    if only:
        files = [f for f in files if f.stem in only]

    ok = fail = skip = 0
    for i, f in enumerate(files, 1):
        stem = f.stem
        if stem in have and not args.force:
            skip += 1
            continue
        try:
            frames, nchunk = upload_one(args.ip, f, stem)
            ok += 1
            print(f"[{i}/{len(files)}] {stem:22s} {frames:>2d}帧 {nchunk:>3d}片 ✓")
        except Exception as e:                      # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(files)}] {stem:22s} ✗ {e}")

    st, body = get(f"http://{args.ip}/diallist", timeout=10)
    total = len(json.loads(body).get("dials", [])) if st == 200 else -1
    print(f"\n完成：新传 {ok}，跳过 {skip}，失败 {fail}；FS 表现共 {total} 个")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
