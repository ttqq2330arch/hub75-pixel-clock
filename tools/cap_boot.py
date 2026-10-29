import sys, time, serial

port = sys.argv[1] if len(sys.argv) > 1 else "COM17"
dur = int(sys.argv[2]) if len(sys.argv) > 2 else 18
baud = 115200

ser = serial.Serial(port, baud, timeout=0.1)
# RTS/DTR toggle to force a clean reset (catch fresh boot)
ser.dtr = False
ser.rts = True
time.sleep(0.15)
ser.rts = False
time.sleep(0.1)

t0 = time.time()
out = []
print("=== capturing %ds on %s ===" % (dur, port))
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
        for line in s.split("\n"):
            if "anim frame" not in line:
                out.append(line + "\n")
                if line.strip():
                    sys.stdout.write(line + "\n")
                    sys.stdout.flush()
ser.close()
open("F:/AI数据/hub75-pixel-clock/tools/boot_capture.txt", "w", encoding="utf-8").write("".join(out))
print("\n=== saved boot_capture.txt ===")
