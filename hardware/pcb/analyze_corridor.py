# -*- coding: utf-8 -*-
"""
analyze_corridor.py — 分析 J3 排针列的横向穿越通道

问题：3V3 需要从 J1-2 (2.27, 4.42) 走到 J4-1 (27.40, 5.60)，
      必须横穿 J3 那 21 个通孔焊盘列 (x=25.13, 贯穿全高)。
本脚本算出：J3 相邻焊盘之间的横向缝隙清单 + 每条缝隙是否已被其他网络占用，
并找出从 x=2.27 到 x=27.40 的可用水平走廊。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

J3_X = 25.13
PAD_D = 1.6
PITCH = 2.54
CLEAR = 0.2          # DRC 间距
TRK_W = 0.2          # Freerouting 实际走线宽度

# ---- J3 焊盘 y 列表 ----
j3 = []
for fp in b.GetFootprints():
    if fp.GetReference() == 'J3':
        for p in fp.Pads():
            j3.append((p.GetNumber(), p.GetPosition().x / NM, p.GetPosition().y / NM))
j3.sort(key=lambda t: t[2])

print('=== J3 横向缝隙（焊盘之间）===')
gaps = []
for i in range(len(j3) - 1):
    y_lo = j3[i][2] + PAD_D / 2
    y_hi = j3[i + 1][2] - PAD_D / 2
    width = y_hi - y_lo
    # 可用线中心范围
    c_lo = y_lo + CLEAR + TRK_W / 2
    c_hi = y_hi - CLEAR - TRK_W / 2
    gaps.append((i, y_lo, y_hi, width, c_lo, c_hi))
    mark = 'OK ' if width >= TRK_W + 2 * CLEAR else 'NG '
    print('  %s缝隙%d: y %.2f..%.2f 宽 %.2fmm  线中心可放 %.2f..%.2f'
          % (mark, i, y_lo, y_hi, width, c_lo, c_hi))

# ---- 收集所有走线（含过孔），按层 ----
segs = []      # (layer, net, x1,y1,x2,y2, width)
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    lay = t.GetLayer()
    if t.GetClass() == 'PCB_VIA':
        w = 0.8
    else:
        w = t.GetWidth() / NM
    segs.append((lay, t.GetNetname(), s.x / NM, s.y / NM, e.x / NM, e.y / NM, w))

# ---- 对每条缝隙，检查 x∈[24.0,26.3] 区间内是否有走线穿过 ----
print()
print('=== 各缝隙的占用情况（x 24.0..26.3 区间）===')
free_gaps = []
for (i, y_lo, y_hi, width, c_lo, c_hi) in gaps:
    if width < TRK_W + 2 * CLEAR:
        continue
    blocked = []
    for (lay, net, x1, y1, x2, y2, w) in segs:
        # 只关心跨越 J3 列的线段（x 区间覆盖 24.0..26.3）
        if max(x1, x2) < 24.0 or min(x1, x2) > 26.3:
            continue
        # 线段与 y 带的相交
        lo, hi = min(y1, y2), max(y1, y2)
        half = w / 2
        if lo - half < y_hi and hi + half > y_lo:
            blocked.append((net, lay, round(lo, 2), round(hi, 2)))
    if blocked:
        print('  缝隙%d (y %.2f..%.2f) 被占: %s' % (i, y_lo, y_hi, blocked))
    else:
        print('  缝隙%d (y %.2f..%.2f) **空闲**' % (i, y_lo, y_hi))
        free_gaps.append((i, y_lo, y_hi, c_lo, c_hi))

print()
print('空闲缝隙数:', len(free_gaps))
for (i, y_lo, y_hi, c_lo, c_hi) in free_gaps:
    print('   #%d  y %.2f..%.2f  可放中心 %.2f..%.2f' % (i, y_lo, y_hi, c_lo, c_hi))
