# -*- coding: utf-8 -*-
"""
verify_firmware_match.py — 转接板网表 vs 固件 config.h 逐项对照（按 GPIO 链）

★ 正确的验证链（三段都必须成立，固件才能零改动）
  ① 板子：DevKit 排针脚（J1/J3）承载的 GPIO → 网络名
  ② 固件：config.h 的 PIN_<信号> = GPIO 编号
  ③ 屏侧：J2（HUB75 排母）针号 → 网络名 → 经「奇偶翻插」→ 屏标准针号

  完整链条例（G1）：
     DevKit J1-5 (GPIO5) ──[板内走线]──> J2-1 (G1) ──[排线翻插 奇+1]──> 屏2 (G1)
     固件 PIN_G1 = 5 = GPIO5  ✓ 三段一致

★ 排线翻插规则（config.h 注释 + gen_board.py J2_SCREEN）：
  板针 n → 屏针 n±1（奇→+1，偶→-1）
"""
import re

import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
FW = r'F:/AI数据/hub75-pixel-clock/src/config.h'
NM = 1_000_000.0

# ------------------------------------------------------------------
# 屏侧标准 HUB75 针序（config.h 注释）
#   1=R1 2=G1 3=B1 4=GND 5=R2 6=G2 7=B2 8=E 9=A 10=B 11=C 12=D
#   13=CLK 14=LAT 15=OE 16=GND
# ------------------------------------------------------------------
SCREEN_NET = {1: 'R1', 2: 'G1', 3: 'B1', 4: 'GND', 5: 'R2', 6: 'G2',
              7: 'B2', 8: 'E', 9: 'A', 10: 'B', 11: 'C', 12: 'D',
              13: 'CLK', 14: 'LAT', 15: 'OE', 16: 'GND'}

# 板针 n → 屏针（奇→+1，偶→-1）
J2_SCREEN = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7,
             9: 10, 10: 9, 11: 12, 12: 11, 13: 14, 14: 13, 15: 16, 16: 15}

# DevKit 排针脚 → GPIO（ESP32-S3-DevKitC-1 官方脚序，gen_board.py 同源）
J1_GPIO = {1: '3V3', 2: '3V3', 3: 'RST', 4: 4, 5: 5, 6: 6, 7: 7, 8: 15,
           9: 16, 10: 17, 11: 18, 12: 8, 13: 3, 14: 46, 15: 9, 16: 10,
           17: 11, 18: 12, 19: 13, 20: 14, 21: '5V', 22: 'GND'}
J3_GPIO = {1: 'GND', 2: 43, 3: 44, 4: 1, 5: 2, 6: 42, 7: 41, 8: 40,
           9: 39, 10: 38, 11: 37, 12: 36, 13: 35, 14: 0, 15: 45,
           16: 48, 17: 47, 18: 21, 19: 20, 20: 19, 21: 'GND', 22: 'GND'}

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
pad_net = {}
for fp in b.GetFootprints():
    for p in fp.Pads():
        pad_net[(fp.GetReference(), p.GetNumber())] = p.GetNetname()

src = open(FW, encoding='utf-8').read()
DEF_RE = re.compile(r'#define\s+PIN_([A-Z0-9_]+)\s+(\d+)')
defines = {m.group(1): int(m.group(2)) for m in DEF_RE.finditer(src)}

print('=' * 88)
print('=== ① 固件 config.h 的 PIN 定义 ===')
for k in ('R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'A', 'B', 'C', 'D', 'E',
          'LAT', 'OE', 'CLK', 'SDA', 'SCL'):
    print('   PIN_%-4s = %s' % (k, defines.get(k, '(未定义)')))

# ------------------------------------------------------------------
# 反查：每个 GPIO 在 DevKit 排针上的位置
# ------------------------------------------------------------------
gpio_to_j1 = {}
for pin, g in J1_GPIO.items():
    if isinstance(g, int):
        gpio_to_j1.setdefault(g, []).append(('J1', pin))
gpio_to_j3 = {}
for pin, g in J3_GPIO.items():
    if isinstance(g, int):
        gpio_to_j3.setdefault(g, []).append(('J3', pin))

print()
print('=' * 88)
print('=== ② 完整链条验证：GPIO → 板排针 → 板内走线 → J2 针 → 翻插 → 屏针 ===')
print()
print('  信号   GPIO   DevKit针      板排针网络   J2针   J2网络   屏针  屏网络   判定')
print('  ' + '-' * 84)

fails = []
for sig in ('R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'A', 'B', 'C', 'D', 'E',
            'CLK', 'LAT', 'OE'):
    gpio = defines.get(sig)
    if gpio is None:
        fails.append((sig, '固件未定义 PIN_%s' % sig))
        continue

    # ②a GPIO 在 DevKit 哪根排针上
    src_pins = []
    for (ref, pin) in gpio_to_j1.get(gpio, []):
        src_pins.append((ref, pin))
    for (ref, pin) in gpio_to_j3.get(gpio, []):
        src_pins.append((ref, pin))

    devkit_txt = ','.join('%s-%d' % p for p in src_pins) or '(未找到)'
    net_at_devkit = ''
    for (ref, pin) in src_pins:
        n = pad_net.get((ref, str(pin)), '')
        if n:
            net_at_devkit = n
            break

    # ②b J2 上承载该网络的是哪一针
    j2_pin = None
    for pin in range(1, 17):
        if pad_net.get(('J2', str(pin))) == sig:
            j2_pin = pin
            break

    if j2_pin is None:
        fails.append((sig, 'J2 上找不到网络 %s' % sig))
        print('  %-5s %5s %-14s %12s %6s %8s %6s %8s   <<< J2 无此网络'
              % (sig, gpio, devkit_txt, net_at_devkit, '-', '-', '-', '-'))
        continue

    screen_pin = J2_SCREEN[j2_pin]
    screen_net = SCREEN_NET[screen_pin]

    # ③ 判定
    ok_devkit = (net_at_devkit == sig)
    ok_screen = (screen_net == sig)
    ok = ok_devkit and ok_screen
    if not ok:
        fails.append((sig, 'DevKit侧=%s 屏侧=%s' % (net_at_devkit, screen_net)))

    print('  %-5s %5d %-14s %12s %6d %8s %6d %8s   %s'
          % (sig, gpio, devkit_txt, net_at_devkit or '(空)', j2_pin, sig,
             screen_pin, screen_net,
             'OK' if ok else ('<<< DevKit侧不符' if not ok_devkit
                              else '<<< 屏侧不符')))

print()
print('=' * 88)
print('=== ③ 特殊信号核查 ===')
# GND
j2_gnd = sorted(p for p in range(1, 17) if pad_net.get(('J2', str(p))) == 'GND')
j2_gnd_screen = sorted(J2_SCREEN[p] for p in j2_gnd)
print('  J2 的 GND 针:', j2_gnd, '→ 翻插后屏针', j2_gnd_screen,
      '（屏标准 GND 在 4/16）', 'OK' if j2_gnd_screen == [4, 16] else '<<< 不符')
if j2_gnd_screen != [4, 16]:
    fails.append(('GND', '屏侧 GND 位置 %s' % j2_gnd_screen))

j1_gnd = sorted(p for p in range(1, 23) if pad_net.get(('J1', str(p))) == 'GND')
j3_gnd = sorted(p for p in range(1, 23) if pad_net.get(('J3', str(p))) == 'GND')
print('  J1 的 GND 针:', j1_gnd or '(无)', '（DevKit 22=GND，未引出属正常）')
print('  J3 的 GND 针:', j3_gnd, '（DevKit 1=GND, 21=GND）')

# 3V3
v3 = sorted(k for k, v in pad_net.items() if v == '3V3')
print('  3V3 焊盘:', v3)
if ('J4', '1') not in v3:
    fails.append(('3V3', 'J4-1 无 3V3'))

# I2C
sda = sorted(k for k, v in pad_net.items() if v == 'SDA')
scl = sorted(k for k, v in pad_net.items() if v == 'SCL')
print('  SDA 焊盘:', sda, '（J3-7=GPIO41=I2C_SDA, J4-3=I2C 排针）')
print('  SCL 焊盘:', scl, '（J3-6=GPIO42=I2C_SCL, J4-4=I2C 排针）')
if ('J3', '7') not in sda or ('J4', '3') not in sda:
    fails.append(('SDA', sda))
if ('J3', '6') not in scl or ('J4', '4') not in scl:
    fails.append(('SCL', scl))

# UART 测试点
utx = sorted(k for k, v in pad_net.items() if v == 'UTX')
urx = sorted(k for k, v in pad_net.items() if v == 'URX')
print('  UTX 焊盘:', utx, '（J3-2=GPIO43, J5-1=UART 测试点）')
print('  URX 焊盘:', urx, '（J3-3=GPIO44, J5-2=UART 测试点）')

print()
print('=' * 88)
if fails:
    print('!! 发现 %d 处问题：' % len(fails))
    for f in fails:
        print('   ', f)
else:
    print('>>> 板子网表与固件 config.h 完全一致')
    print('>>> 13 根 HUB75 信号 + GND 的 GPIO→板内→J2→翻插→屏针 全链条一致')
    print('>>> ⇒ 固件零改动即可驱动新板')
print('=' * 88)
