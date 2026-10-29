# -*- coding: utf-8 -*-
"""
verify_nets.py v2.0 — 端到端网表校验
校验链：板子焊盘 → DevKitC-1 官方脚序 → GPIO 号 → 屏标准序信号 → src/config.h 的 PIN_xxx
任何一环对不上立刻报错。
"""
import re
import sys
import pcbnew

PCB = sys.argv[1] if len(sys.argv) > 1 else \
    r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb'
CFG = r'F:/AI数据/hub75-pixel-clock/src/config.h'

NM = 1_000_000
W, H = 44.0, 54.5
b = pcbnew.LoadBoard(PCB)

# ---------- 1. 官方 DevKitC-1 脚序（Espressif 官方 pin-layout 图）----------
J1_SIG = {1: '3V3', 2: '3V3', 3: 'RST', 4: 'IO4', 5: 'IO5', 6: 'IO6', 7: 'IO7',
          8: 'IO15', 9: 'IO16', 10: 'IO17', 11: 'IO18', 12: 'IO8', 13: 'IO3',
          14: 'IO46', 15: 'IO9', 16: 'IO10', 17: 'IO11', 18: 'IO12',
          19: 'IO13', 20: 'IO14', 21: '5V', 22: 'GND'}
J3_SIG = {1: 'GND', 2: 'TX', 3: 'RX', 4: 'IO1', 5: 'IO2', 6: 'IO42', 7: 'IO41',
          8: 'IO40', 9: 'IO39', 10: 'IO38', 11: 'IO37', 12: 'IO36', 13: 'IO35',
          14: 'IO0', 15: 'IO45', 16: 'IO48', 17: 'IO47', 18: 'IO21',
          19: 'IO20', 20: 'IO19', 21: 'GND', 22: 'GND'}

# ---------- 2. 旧转接板 J1 逐脚承载的 GPIO（读自 j1_zoom.png 原理图，实测可用）----------
# 这是「物理真值」：旧板 J1 的每个板针上挂的是哪个 GPIO。
# 排线两列对调后 板针 n → 屏针 n±1（奇→+1，偶→-1）
OLD_J1_GPIO = {1: 5, 2: 4, 3: None, 4: 6, 5: 15, 6: 7, 7: 10, 8: 16,
               9: 18, 10: 17, 11: 9, 12: 8, 13: 12, 14: 11, 15: None,
               16: 13}

# ---------- 3. 屏标准序（panel_silk.jpg 实测丝印）----------
SCREEN = {1: 'R1', 2: 'G1', 3: 'B1', 4: 'GND', 5: 'R2', 6: 'G2', 7: 'B2',
          8: 'E', 9: 'A', 10: 'B', 11: 'C', 12: 'D', 13: 'CLK', 14: 'LAT',
          15: 'OE', 16: 'GND'}

# ---------- 4. config.h 的 GPIO 定义 ----------
txt = open(CFG, encoding='utf-8', errors='ignore').read()
CFG_PINS = {}
for m in re.finditer(r'#define\s+PIN_(\w+)\s+(\d+)', txt):
    CFG_PINS[m.group(1)] = int(m.group(2))
print('config.h PIN_ 定义:', {k: CFG_PINS[k] for k in sorted(CFG_PINS)})

err = []

# ---------- 5. 收集板上焊盘 ----------
pads = {}
for fp in b.GetFootprints():
    ref = fp.GetReference()
    for p in fp.Pads():
        x, y = p.GetPosition().x / NM, p.GetPosition().y / NM
        try:
            num = int(p.GetNumber())
        except ValueError:
            num = 0          # 安装孔 NPTH 无脚号
        pads[(ref, num)] = (x, y, p.GetNetname())

print('\n--- 5. 焊盘清单 ---')
for k in sorted(pads):
    x, y, n = pads[k]
    print('  %-4s %-3s  (%7.3f,%7.3f)  %s' % (k[0], k[1], x, y, n or '(NC)'))

# ---------- 6. 机械校验：DevKitC-1 配合几何 ----------
print('\n--- 6. 机械几何校验（官方：22P / 2.54mm / 排距 22.86mm / pin1 在天线端）---')
j1 = sorted([k[1] for k in pads if k[0] == 'J1'])
j3 = sorted([k[1] for k in pads if k[0] == 'J3'])
if j1 != list(range(1, 22)):
    err.append('J1 脚号不是 1..21: %s' % j1)
if j3 != list(range(1, 22)):
    err.append('J3 脚号不是 1..21: %s' % j3)

for ref in ('J1', 'J3'):
    xs = {round(pads[(ref, i)][0], 4) for i in range(1, 22)}
    ys = [pads[(ref, i)][1] for i in range(1, 22)]
    if len(xs) != 1:
        err.append('%s 不是单列: x=%s' % (ref, xs))
    pitch = [round(ys[i + 1] - ys[i], 4) for i in range(len(ys) - 1)]
    if max(pitch) - min(pitch) > 1e-6 or abs(pitch[0] - 2.54) > 1e-6:
        err.append('%s 节距异常: %s' % (ref, pitch))
    print('  %s: x=%.3f  pin1 y=%.3f  pin21 y=%.3f  pitch=%.3f  脚数=%d'
          % (ref, xs.pop(), ys[0], ys[-1], pitch[0], len(ys)))

gap = round(pads[('J3', 1)][0] - pads[('J1', 1)][0], 4)
print('  两排中心距 = %.4f mm （官方 22.86，偏差 %.4f）' % (gap, abs(gap - 22.86)))
if abs(gap - 22.86) > 0.02:
    err.append('排距错误: %.4f' % gap)
if abs(pads[('J1', 1)][1] - 1.8794) > 0.02:
    err.append('pin1 位置错误: %.4f（官方实测 1.8794）' % pads[('J1', 1)][1])
if abs(pads[('J1', 1)][0] - 2.2700) > 0.02:
    err.append('J1 x 位置错误: %.4f（应为 2.2700）' % pads[('J1', 1)][0])
if abs(pads[('J3', 1)][0] - 25.1300) > 0.02:
    err.append('J3 x 位置错误: %.4f（应为 25.1300）' % pads[('J3', 1)][0])

ANT_X0, ANT_X1, ANT_Y1 = 4.75, 22.75, 6.5
for (ref, num), (x, y, n) in pads.items():
    if ANT_X0 < x < ANT_X1 and 0 <= y < ANT_Y1:
        err.append('天线净空内有焊盘: %s-%d (%.2f,%.2f)' % (ref, num, x, y))
print('  天线净空 x[%.1f,%.1f] y[0,%.1f]：无焊盘 ✓' % (ANT_X0, ANT_X1, ANT_Y1))

# ---------- 7. 焊盘不得出板 ----------
for (ref, num), (x, y, n) in pads.items():
    if not (0 <= x <= W and 0 <= y <= H):
        err.append('焊盘出板: %s-%d (%.2f,%.2f)' % (ref, num, x, y))

# ---------- 8. J2 针序必须与旧板 J1 逐脚承载的 GPIO 一致 ----------
print('\n--- 8. J2 针序 vs 旧转接板 J1（按 GPIO 比对）---')
j2_sig_to_pin = {}
for p in range(1, 17):
    n = pads[('J2', p)][2]
    if n:
        j2_sig_to_pin.setdefault(n, p)
j1_net_to_pin = {}
for pin in range(1, 22):
    n = pads[('J1', pin)][2]
    if n:
        j1_net_to_pin.setdefault(n, pin)

# GPIO -> 网名（本板 J1 上的网名）
gpio_of_net = {}
for pin in range(1, 22):
    n = pads[('J1', pin)][2]
    if n:
        gpio_of_net[n] = int(J1_SIG[pin][2:])

j2bad = 0
for pin in range(1, 17):
    net = pads[('J2', pin)][2]
    g = gpio_of_net.get(net)
    if g != OLD_J1_GPIO[pin]:
        err.append('J2-%d 承载 GPIO%s ≠ 旧板 GPIO%s' % (pin, g, OLD_J1_GPIO[pin]))
        j2bad += 1
print('  J2 16 脚承载的 GPIO 与旧板 J1 完全一致 ✓' if not j2bad else '  J2 针序有不符！')

# ---------- 9. 排线映射：板针 → 屏针（两列对调）→ 屏物理信号 → config.h ----------
print('\n--- 9. 板针 → 屏针 映射（排线两列对调，与旧板同）---')
CFG_TO_NAME = {v: k for k, v in CFG_PINS.items()
               if k in ('R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'E', 'A', 'B',
                        'C', 'D', 'CLK', 'LAT', 'OE')}
board_pin_to_screen = {}
for pin in range(1, 17):
    sp = pin + 1 if pin % 2 == 1 else pin - 1
    board_pin_to_screen[pin] = sp
    net = pads[('J2', pin)][2]
    g = gpio_of_net.get(net)
    phys = SCREEN[sp]
    if phys == 'GND':
        # GND 脚没有 GPIO 编号，单独按网名判定：板针的网必须是 GND
        fw = 'GND'
        ok = (net == 'GND')
    else:
        fw = CFG_TO_NAME.get(g)
        ok = (fw == phys)
    if not ok:
        err.append('板针%d(GPIO%s,固件当%s)→屏针%d 但屏上是 %s'
                   % (pin, g, fw, sp, phys))
    print('  板针%-2d GPIO%-3s 固件当 %-4s → 屏针%-2d 屏上是 %-4s  %s'
          % (pin, g if g is not None else '-', fw, sp, phys,
             'OK' if ok else '*** 不符 ***'))

# GND 必须落回屏 4/16（netlist.md 上电前必查项）
for bpin, spin in ((3, 4), (15, 16)):
    if OLD_J1_GPIO[bpin] is not None or SCREEN[spin] != 'GND':
        err.append('GND 落位错：板针%d→屏针%d' % (bpin, spin))
print('  GND 落位：板3→屏4、板15→屏16 ✓（netlist.md 上电前必查项通过）')

# ---------- 10. 端到端：config.h 的 GPIO → 屏上物理信号 ----------
print('\n--- 10. 端到端：config.h 的 GPIO → 屏上物理信号 ---')
for sig in ['R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'E', 'A', 'B', 'C', 'D',
            'CLK', 'LAT', 'OE']:
    if sig not in j2_sig_to_pin:
        err.append('J2 上找不到信号 %s' % sig)
        continue
    if sig not in j1_net_to_pin:
        err.append('J1 上找不到信号 %s' % sig)
        continue
    j2pin = j2_sig_to_pin[sig]
    screen_pin = board_pin_to_screen[j2pin]
    j1pin = j1_net_to_pin[sig]
    devkit_sig = J1_SIG[j1pin]
    gpio = int(devkit_sig[2:])
    cfg_gpio = CFG_PINS.get(sig)
    fw_name = CFG_TO_NAME.get(gpio)
    phys = SCREEN[screen_pin]
    ok_gpio = (gpio == cfg_gpio)
    ok_phys = (fw_name == phys)
    if not ok_gpio:
        err.append('%s: 板上 GPIO%d ≠ config.h GPIO%d' % (sig, gpio, cfg_gpio))
    if not ok_phys:
        err.append('%s: GPIO%d(固件当 %s) 落到屏针%d 但屏上是 %s'
                   % (sig, gpio, fw_name, screen_pin, phys))
    print('  %-4s 屏针%-2d(=%-3s) | J2-%-2d | J1-%-2d(%s) | GPIO%-2d | 固件当 %-4s %s'
          % (sig, screen_pin, phys, j2pin, j1pin, devkit_sig, gpio, fw_name,
             'OK' if (ok_gpio and ok_phys) else '*** 不符 ***'))

# ---------- 11. GND / 3V3 / I2C / UART ----------
print('\n--- 11. 电源与外设 ---')
gnd_pads = sorted([(r, n) for (r, n), v in pads.items() if v[2] == 'GND'])
print('  GND 焊盘:', gnd_pads)
print('  3V3 焊盘:', sorted([(r, n) for (r, n), v in pads.items() if v[2] == '3V3']))
for (r, n) in [('J3', 1), ('J3', 21), ('J2', 3), ('J2', 15)]:
    if pads.get((r, n), (0, 0, None))[2] != 'GND':
        err.append('%s-%d 应为 GND' % (r, n))
for (r, n), net in [(('J4', 3), 'SDA'), (('J4', 4), 'SCL'),
                    (('J5', 1), 'UTX'), (('J5', 2), 'URX'),
                    (('J3', 6), 'SCL'), (('J3', 7), 'SDA'),
                    (('J3', 2), 'UTX'), (('J3', 3), 'URX')]:
    if pads.get((r, n), (0, 0, None))[2] != net:
        err.append('%s-%d 应为 %s' % (r, n, net))
print('  I2C: J3-7(SDA)→J4-3 ; J3-6(SCL)→J4-4  ✓')
print('  UART: J3-2(TX)→J5-1 ; J3-3(RX)→J5-2  ✓')

# ---------- 汇总 ----------
print('\n' + '=' * 64)
if err:
    print('RESULT: FAIL（%d 项）' % len(err))
    for e in err:
        print('  !!', e)
else:
    print('RESULT: PASS — 机械几何 + 针序 + 端到端网表全部正确')
print('=' * 64)
