# -*- coding: utf-8 -*-
"""
probe_lane.py — 找出 J1→J4 水平走廊上真正可用的行车道

背景：
  3V3 需要从 J1-2 (2.27, 4.42) 走到 J4-1 (27.40, 5.60)。
  J3 那 21 个通孔焊盘列 (x=25.13) 横在中间，必须从缝隙穿过。
  缝隙 = 2.54 - 1.6 = 0.94mm，0.2mm 线 + 2×0.2mm 间距 = 0.6mm ⇒ 几何上可过。
  但 Freerouting 找不到。本脚本扫描 F.Cu 实际占用，给出可用的行车道 (lane)。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

PAD_R = 0.8
CLEAR = 0.2
TRK_W = 0.2


def segs_on(layer):
    out = []
    for t in b.GetTracks():
        if t.GetLayer() != layer:
            continue
        s, e = t.GetStart(), t.GetEnd()
        w = 0.8 if t.GetClass() == 'PCB_VIA' else t.GetWidth() / NM
        out.append((t.GetNetname(), s.x / NM, s.y / NM, e.x / NM, e.y / NM, w))
    return out


def pads_all():
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pos = p.GetPosition()
            out.append((fp.GetReference() + '-' + p.GetNumber(),
                        pos.x / NM, pos.y / NM, PAD_R))
    return out


F = segs_on(pcbnew.F_Cu)
B = segs_on(pcbnew.B_Cu)
P = pads_all()

# 目标：在 F.Cu 上找一条从 x=2.6 到 x=24.0 的水平行车道，
#       且该车道穿过 J3 列时正好落在 J3 的某个缝隙里
print('=== F.Cu 在 x∈[2.6, 24.0] 区间、y∈[0,8] 的所有走线 ===')
for (net, x1, y1, x2, y2, w) in sorted(F, key=lambda t: min(t[1], t[3])):
    if max(x1, x2) < 2.4 or min(x1, x2) > 24.2:
        continue
    if max(y1, y2) > 8.5:
        continue
    print('  %-5s (%.2f,%.2f)->(%.2f,%.2f) w=%.2f' % (net, x1, y1, x2, y2, w))

print()
print('=== 焊盘在 x∈[2.0,24.5], y∈[0,8] 的（会阻挡水平车道）===')
for (nm, x, y, r) in sorted(P, key=lambda t: (t[1], t[2])):
    if x < 2.0 or x > 24.5 or y > 8.0:
        continue
    print('  %-8s (%.2f, %.2f) r=%.2f  占 y %.2f..%.2f'
          % (nm, x, y, r, y - r, y + r))

print()
print('=== J3 缝隙（仅列 y<9 的）===')
for i in range(1, 5):
    pass
# J3 焊盘 y
j3y = [1.88 + k * 2.54 for k in range(21)]
for i in range(len(j3y) - 1):
    if j3y[i] > 9:
        break
    lo, hi = j3y[i] + 0.8, j3y[i + 1] - 0.8
    print('  缝隙%d y %.2f..%.2f 宽 %.2f  线中心 %.2f..%.2f'
          % (i, lo, hi, hi - lo, lo + CLEAR + TRK_W / 2, hi - CLEAR - TRK_W / 2))
