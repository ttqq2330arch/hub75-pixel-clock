# -*- coding: utf-8 -*-
"""diag_gnd.py — 诊断 GND 焊盘与铺铜的连接断裂点"""
import pcbnew
from pcbnew import VECTOR2I

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

print('=== 焊盘类型统计 ===')
attr_name = {0: 'PTH', 1: 'SMD', 2: 'CONN', 3: 'NPTH'}
type_cnt = {}
gnd_pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        a = p.GetAttribute()
        type_cnt[a] = type_cnt.get(a, 0) + 1
        if p.GetNetname() == 'GND':
            pos = p.GetPosition()
            gnd_pads.append((fp.GetReference(), p.GetNumber(), p, pos.x / NM, pos.y / NM))
for a, c in sorted(type_cnt.items()):
    print('  attr=%d(%s): %d' % (a, attr_name.get(a, '?'), c))

print()
print('=== GND 焊盘清单 ===')
for (ref, num, p, x, y) in sorted(gnd_pads, key=lambda t: (t[0], t[1])):
    print('  %s-%-3s (%7.2f, %7.2f)  attr=%d  pad=%s  drill=%.2f'
          % (ref, num, x, y, p.GetAttribute(), p.GetShape(),
             p.GetDrillSize().x / NM))

print()
print('=== B.Cu 铺铜填充检查 ===')
for z in b.Zones():
    print('  zone layer=%d net=%s  pad_conn=%d  clearance=%.2f  minthick=%.2f'
          % (z.GetLayer(), z.GetNetname(), z.GetPadConnection(),
             z.GetLocalClearance() / NM, z.GetMinThickness() / NM))
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
        if lay not in z.GetLayerSet().Seq():
            continue
        try:
            ps = z.GetFilledPolysList(lay)
            area = ps.Area() / (NM * NM) if ps else 0
            print('     filled @layer %d : outlines=%d area=%.1f mm2'
                  % (lay, ps.OutlineCount() if ps else 0, area))
        except Exception as e:
            print('     layer %d: ERR %s' % (lay, e))

print()
print('=== J3-1 附近 (半径 4mm) 走线 ===')
target = None
for (ref, num, p, x, y) in gnd_pads:
    if ref == 'J3' and num == '1':
        target = (x, y)
print('  J3-1 @', target)
if target:
    tx, ty = target
    for t in b.GetTracks():
        s = t.GetStart()
        e = t.GetEnd()
        d = min(max(s.x / NM, e.x / NM) - tx, 0)  # placeholder
        # 简单判定：端点或中点在 4mm 内
        pts = [(s.x / NM, s.y / NM), (e.x / NM, e.y / NM)]
        near = any(((px - tx) ** 2 + (py - ty) ** 2) ** 0.5 < 4.0 for (px, py) in pts)
        if near:
            kind = 'VIA' if t.GetClass() == 'PCB_VIA' else 'TRACK'
            print('    %-6s %-8s layer=%d (%.2f,%.2f)->(%.2f,%.2f) w=%.2f'
                  % (kind, t.GetNetname(), t.GetLayer(), pts[0][0], pts[0][1],
                     pts[1][0], pts[1][1], t.GetWidth() / NM))

print()
print('=== 连通性检查 (GND 焊盘互相是否连通) ===')
try:
    conn = b.GetConnectivity()
    print('  connectivity obj:', conn)
    for (ref, num, p, x, y) in sorted(gnd_pads, key=lambda t: (t[0], t[1])):
        try:
            pads = conn.GetConnectedPads(p, None)
            others = [q for q in pads if q != p]
            print('    %s-%-3s  连通到 %d 个焊盘: %s'
                  % (ref, num, len(others),
                     ', '.join('%s-%s' % (q.GetParent().GetReference(), q.GetNumber())
                               for q in others[:12])))
        except Exception as e:
            print('    %s-%-3s  ERR %s' % (ref, num, e))
            break
except Exception as e:
    print('  ERR', e)
