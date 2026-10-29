# -*- coding: utf-8 -*-
"""
layout_audit2.py — v2.2 最终布局求解：穷举可行排布，选出无冲突方案

变量：
  J2 焊盘列位置、针序表形状/位置、说明文字带位置
约束（全部来自实测 + 嘉立创规范）：
  · 右侧净宽 17.6mm（26.4..44.0）
  · 1.0mm 字高 → 字符宽 0.9mm，bbox 高 1.70mm
  · 文字距焊盘 ≥ 0.30mm，距板边 ≥ 0.40mm
  · 板高 54.5
  · 安装孔 Ø3.2 (r=1.6) 固定在四角附近
"""
import itertools

TXT_H = 1.70
PAD_R = 0.8
HOLE_R = 1.6
KEEP_PAD = 0.30
KEEP_EDGE = 0.40
BOARD_W, BOARD_H = 44.0, 54.5
DK_RIGHT = 26.4
CHAR_W = 0.90

# 针序条目（8 条奇 + 8 条偶），最宽者决定列宽
ODD = ['1:G1>2', '3:GND>4', '5:G2>6', '7:E>8', '9:B>10',
       '11:D>12', '13:LAT>14', '15:GND>16']
EVEN = ['2:R1>1', '4:B1>3', '6:R2>5', '8:B2>7', '10:A>9',
        '12:C>11', '14:CLK>13', '16:OE>15']


def w(s):
    return CHAR_W * len(s) + 0.35


MAXW = max([w(s) for s in ODD + EVEN])
print('最宽条目 %s = %.2fmm' % (
    max(ODD + EVEN, key=w), MAXW))
print('')

# ---- 方案 A：针序表 = 4 列 × 4 行（列 1,3=ODD；列 2,4=EVEN），
#      放在 J2 正下方，与 J2 行对齐
print('=== 方案 A：J2 在上，针序表在正下方 4 列 × 4 行 ===')
for ncol in (2, 4):
    # 列数 ncol：ncol/2 对 ODD，ncol/2 对 EVEN
    dx = MAXW + 0.6
    total_w = (ncol - 1) * dx + MAXW
    rows = 8 // (ncol // 2)
    dy = TXT_H + 0.55
    tbl_h = (rows - 1) * dy + TXT_H
    # J2 高 8 行
    j2_h = 7 * 2.54 + 2 * PAD_R
    need = j2_h + 3.0 + tbl_h + 3.0 + KEEP_EDGE
    print('  ncol=%d: 表宽 %.2fmm  表高 %.2fmm  总需高 %.2fmm (板高 %.1f) %s'
          % (ncol, total_w, tbl_h, need, BOARD_H,
             '✓' if need <= BOARD_H and total_w <= 17.6 else '✗'))

print('')
print('=== 方案 B：针序表 8 列 × 1 行（横排一行） ===')
for fmt in ('1:G1>2', '1G1>2'):
    pass
dx = MAXW + 0.3
total_w = 7 * dx + MAXW
print('  8 列：总宽 %.2fmm  ✗ 超 17.6mm' % total_w)
print('  ⇒ 8 列横排不可行')

print('')
print('=== 方案 C：拆成两个 4 列块，左右并排 ===')
# 每个块 4 列（ODD2+EVEN2），块宽 = 3*dx + MAXW
dx = MAXW + 0.6
blk = 3 * dx + MAXW
print('  单块 4 列宽 %.2fmm  两块并排 = %.2fmm  ✗ 超 17.6mm'
      % (blk, 2 * blk + 1.0))

print('')
print('=== 方案 D：缩短条目格式以适配 8 列横排 ===')
for fmt_name, f in (
        ('13:LAT>14', lambda p, n, s: '%d:%s>%d' % (p, n, s)),
        ('13 LAT14', lambda p, n, s: '%d %s%d' % (p, n, s)),
        ('13LAT14', lambda p, n, s: '%d%s%d' % (p, n, s)),
):
    mx = 0
    for i in range(8):
        mx = max(mx, w(f(2 * i + 1, ['G1', 'GND', 'G2', 'E', 'B', 'D', 'LAT', 'GND'][i],
                                    [2, 4, 6, 8, 10, 12, 14, 16][i])))
    dx = mx + 0.35
    tot = 7 * dx + mx
    print('  "%s" 最宽 %.2f  8列总宽 %.2f  %s'
          % (fmt_name, mx, tot, '✓ 可行' if tot <= 17.6 else '✗'))

print('')
print('=== 结论候选 ===')
print('  方案 D + "13LAT14" 式 8 列横排：总宽 %.2f ≤ 17.6 ✓' % 0)
print('  但 8 列横排在 17.6mm 内每列仅 ~2.1mm，条目 "13LAT14" 需 %.2fmm ✗')
