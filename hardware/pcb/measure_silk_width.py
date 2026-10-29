# -*- coding: utf-8 -*-
"""measure_silk_width.py — 实测 KiCad 默认字体在指定字高下的字符串宽度

用途：嘉立创要求字符高度 ≥1.0mm，但 1.0mm 字高下字符很宽，
右侧区域只有 17.6mm（DevKit 右缘 26.4 → 板边 44.0），必须先量出真实宽度
才能排布。测完再定稿。
"""
import pcbnew
from pcbnew import PCB_TEXT, VECTOR2I

NM = 1_000_000
board = pcbnew.NewBoard('m')

CANDS = [
    'HUB75 ADAPTER v2.2',
    'ESP32-S3-DEVKITC-1 HAT',
    'ESP32-S3-DEVKITC',
    'CABLE: FLIP 2 COLUMNS',
    'FLIP 2 COLUMNS',
    'SAME INSERTION AS OLD PCB',
    'SAME AS OLD PCB',
    'PIN1=TOP ROW 22.86',
    'PIN1 = TOP',
    'DEVKIT USB AT BOTTOM',
    'PIN:NET>PANEL PIN',
    '13:LAT', '15:GND', '14:CLK', '1:G1', '2:R1',
    'ODD', 'EVEN',
    '1:3V3 2:GND', '3:SDA 4:SCL',
    'J4 I2C SHT30',
    'J5 UART0 115200',
    '1:TX 2:RX 3:GND',
    'ROW n = PIN 2n-1 | 2n',
    'n = PIN 2n-1 | 2n',
    'I2C', 'UART', 'GND', 'TX', 'RX', 'SDA', 'SCL', '3V3',
]

for size in (1.0, 0.9, 0.8):
    print('===== 字高 %.1fmm / 线宽 0.15mm =====' % size)
    for s in CANDS:
        t = PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(VECTOR2I(0, 0))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(VECTOR2I(int(size * NM), int(size * NM)))
        t.SetTextThickness(int(0.15 * NM))
        board.Add(t)
        b = t.GetBoundingBox()
        w = (b.GetRight() - b.GetLeft()) / NM
        h = (b.GetBottom() - b.GetTop()) / NM
        fit = '  <== 超右侧 17.6mm' if w > 17.6 else ''
        print('  %-26s w=%6.2f h=%5.2f  ch=%4.2f%s'
              % ('"%s"' % s, w, h, w / len(s), fit))
        board.Remove(t)
    print('')
