# -*- coding: utf-8 -*-
"""serial_mon.py — 串口抓取 HUB75 像素时钟日志（CH343，不占端口不放固件）

用法：
  python serial_mon.py            # 抓 8 秒，过滤 anim/boot/DBG 关键行
  python serial_mon.py 15         # 抓 15 秒
  python serial_mon.py 15 all     # 抓 15 秒，打印全部行

2026-10-23：重建（原 F:/hub75-build/m3_listen.py 随构建目录被 pio 清掉）。
"""
import sys
import time

import serial
import serial.tools.list_ports as lp

KEY = ("anim", "ANIM", "DBG", "boot", "MAIN", "WiFi", "STA", "HTTP", "fs",
       "PSRAM", "IP", "push", "BLE", "face", "FACE")


def find_port():
    for p in lp.comports():
        if "1A86:55D3" in (p.hwid or "").upper().replace(" ", ""):
            return p.device
    for p in lp.comports():
        if "303A" in (p.hwid or "").upper():
            return p.device
    return None


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    show_all = len(sys.argv) > 2 and sys.argv[2] == "all"
    port = find_port()
    if not port:
        print("[ERR] 找不到 CH343 / ESP32-S3 串口")
        return 1
    ser = serial.Serial(port, 115200, timeout=0.2, rtscts=False, dsrdtr=False)
    ser.setRTS(False)
    ser.setDTR(False)
    print("[MON] %s, %.0fs" % (port, secs))
    t0 = time.time()
    buf = ""
    while time.time() - t0 < secs:
        n = ser.in_waiting
        if n:
            buf += ser.read(n).decode("utf-8", "replace")
    ser.close()
    for ln in buf.splitlines():
        if show_all or any(k in ln for k in KEY):
            print(ln)
    print("[MON] total %d lines" % len(buf.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
