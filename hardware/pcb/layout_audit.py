# -*- coding: utf-8 -*-
"""
layout_audit.py — 布局坐标冲突预检（生成板之前先算，避免反复生成再渲染）

列出所有关键元素的 y 区间，检查垂直方向是否有重叠。
"""
print('--- 右侧区域（x 26.4..44.0）垂直占用 ---')
items = [
    ('H2 mounting hole (41,3)', 3.0, 3.0),
    ('J4 I2C pads row', 8.0, 8.0),
    ('J4 labels row', 8.0 + 2.3, 8.0 + 2.3),
    ('J5 UART pads row', 13.0, 13.0),
    ('J5 labels row', 13.0 + 2.3, 13.0 + 2.3),
    ('info silk line1', 16.4, 16.4),
    ('info silk line2', 18.8, 18.8),
    ('info silk line3', 21.2, 21.2),
    ('info silk line4', 23.6, 23.6),
    ('info silk line5', 26.0, 26.0),
    ('info silk line6', 28.4, 28.4),
    ('info silk line7', 30.8, 30.8),
    ('J2 row1..row8', 18.5, 18.5 + 7 * 2.54),
    ('TBL hdr2 ODD/EVEN', 38.6 - 5.4, 38.6 - 5.4),
    ('TBL hdr1 format', 38.6 - 3.0, 38.6 - 3.0),
    ('TBL group1 row1..4', 38.6, 38.6 + 3 * 2.6),
    ('TBL group2 row1..4', 38.6 + 4 * 2.6, 38.6 + 7 * 2.6),
    ('H3 mounting hole (29,51.5)', 51.5, 51.5),
]
TXT_H = 1.70     # 1.0mm 字高实测 bbox 高
PAD_R = 0.8      # 焊盘半径
GAP = 0.30       # 文字间最小间隙

for name, y0, y1 in items:
    print('  y=%6.2f..%6.2f  %s' % (y0 - TXT_H / 2, y1 + TXT_H / 2, name))

print('')
print('--- 关键冲突检查 ---')
problems = []

# 1. J2 焊盘 vs 说明文字（说明区 x 26.4..44 全宽，J2 焊盘 x 28.0..32.1 → 必重叠？）
print('J2 焊盘占 y %.2f..%.2f，x 28.0..32.14' % (18.5 - PAD_R, 18.5 + 7 * 2.54 + PAD_R))
print('说明文字 y 15.55..31.65  → 与 J2 焊盘在 y 18.5..36.3 区间、x 上重叠！')
print('  ⇒ 必须让说明文字的 x 区间避开 J2 焊盘的 x 区间 (28.0..32.14)')
print('  ⇒ 右侧区域 x 26.4..44 中，只有 32.14..44.0 = 11.86mm 可用作文字区')
print('  ⇒ 11.86mm / 0.9mm per char ≈ 13 字符/行')
print('')

# 2. 表格宽度检查
print('--- 针序表宽度 ---')
for s in ['13:LAT>14', '15:GND>16', '14:CLK>13', '1:G1>2']:
    w = 0.9 * len(s) + 0.35
    print('  "%s" ≈ %.2fmm' % (s, w))
print('  4 列 × 4.05mm 间距 = 16.2mm，末列起点 27.0+3×4.05=39.15')
print('  末列文本 5.4mm → 右边缘 44.55 > 44.0 板边！✗ 超边')
print('  ⇒ 需要：要么列距缩到 3.7，要么首列左移到 26.6')
for dx in (3.6, 3.7, 3.8):
    x0 = 26.6
    last = x0 + 3 * dx
    print('    x0=26.6 dx=%.1f → 末列 %.2f + 5.4 = %.2f' % (dx, last, last + 5.4))

print('')
print('--- 表格行垂直 ---')
for g in range(2):
    y = 38.6 + g * 4 * 2.6
    print('  组%d: y %.2f .. %.2f' % (g + 1, y, y + 3 * 2.6 + TXT_H / 2))
print('  表格末行底 %.2f，板底 54.5，安装孔(29,51.5) 顶 %.2f'
      % (38.6 + 7 * 2.6 + TXT_H / 2, 51.5 - 1.6))
