import sys, time, serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM17"
dur = int(sys.argv[2]) if len(sys.argv) > 2 else 25
baud = 115200

ser = serial.Serial(port, baud, timeout=0.1)
t0 = time.time()
out = []
print("=== LIVE (no reset) %ds on %s ===" % (dur, port))
while time.time() - t0 < dur:
    try:
        b = ser.read(4096)
    except Exception as e:
        out.append("\n[ERR] " + str(e))
        break
    if b:
        try:
            s = b.decode("utf-8", "replace")
        except Exception:
            s = repr(b)
        # 只保留非动画帧日志，便于看关键事件
        for line in s.split("\n"):
            if "anim frame" not in line:
                if line.strip():
                    print(line)
                out.append(line + "\n")
ser.close()
open("F:/AI数据/hub75-pixel-clock/tools/boot_live.txt", "w", encoding="utf-8").write("".join(out))
print("\n=== saved boot_live.txt ===")
