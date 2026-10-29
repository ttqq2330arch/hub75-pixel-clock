# -*- coding: utf-8 -*-
"""flash_firmware.py — 烧录 HUB75 像素时钟固件（ESP32-S3，CH343 串口）

用法：python flash_firmware.py [COM端口]   不带参数则自动找 CH343

背景：2026-10-23 pio 重建时把旧的 F:/hub75-build/cli_flash3.py 连同整个构建根目录
清了（build_dir 里的非构建文件不要放重要东西！）。本脚本重建，逻辑更简单：
esptool default_reset 一把梭，失败再试 no_reset（需手动按 BOOT+EN）。
"""
import glob
import subprocess
import sys

import serial.tools.list_ports as lp

ESPTOOL = (glob.glob("F:/pio/packages/tool-esptoolpy/esptool.py") or [None])[0]
BD = "F:/hub75-build/esp32-s3"
PY = sys.executable


def find_port():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for p in lp.comports():
        hwid = (p.hwid or "").upper().replace(" ", "")
        if "1A86:55D3" in hwid:      # CH343
            return p.device
    for p in lp.comports():
        if "303A" in (p.hwid or "").upper():   # ESP32-S3 原生 USB
            return p.device
    return None


def flash(port, reset_mode):
    cmd = [
        PY, ESPTOOL,
        "--chip", "esp32s3",
        "--port", port,
        "--baud", "921600",
        "--before", reset_mode,
        "--after", "hard_reset",
        "write_flash",
        "0x0", BD + "/bootloader.bin",
        "0x8000", BD + "/partitions.bin",
        "0x10000", BD + "/firmware.bin",
    ]
    print("[FLASH] " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=BD)
    return r.returncode


def main():
    port = find_port()
    if not port:
        print("[ERR] 找不到 CH343 / ESP32-S3 串口")
        return 1
    if not ESPTOOL:
        print("[ERR] 找不到 esptool.py")
        return 1
    print("[FLASH] port=%s" % port)
    rc = flash(port, "default_reset")
    if rc != 0:
        print("[FLASH] default_reset 失败，尝试 no_reset（请手动按住 BOOT 点一下 EN 进下载模式）...")
        rc = flash(port, "no_reset")
    print("[FLASH] rc=%d" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
