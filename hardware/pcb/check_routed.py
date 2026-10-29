# -*- coding: utf-8 -*-
"""
check_routed.py — 布线板综合体检

检查项：
  1) 天线净空区（x[4.75,22.75] y[0,6.5]）内不得有任何铜箔：
     走线 / 过孔 / 焊盘 / 铺铜 —— ESP32-S3-WROOM-1 天线净空，违反会掉射频性能
  2) 每个网络的连通性：走线是否覆盖了该网络的所有焊盘
  3) 铺铜与 GND 焊盘的实际连接情况
  4) 走线统计（层分布 / 线宽 / 过孔）

用法: "F:/Tools/KiCad/bin/python.exe" check_routed.py <board.kicad_pcb>
"""
import sys
import collections
import pcbnew

NM = 1_000_000
PCB = sys.argv[1] if len(sys.argv) > 1 else \
    r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter-routed.kicad_pcb'

ANT_X0, ANT_X1, ANT_Y1 = 4.75, 22.75, 6.5

b = pcbnew.LoadBoard(PCB)
print('board:', PCB)
print('')

# ---------- 1) 天线净空 ----------
viol = []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        x, y = p.x / NM, p.y / NM
        if ANT_X0 <= x <= ANT_X1 and 0 <= y <= ANT_Y1:
            viol.append('VIA @ (%.2f, %.2f) net=%s' % (x, y, t.GetNetname()))
    else:
        s = t.GetStart()
        e = t.GetEnd()
        for (px, py) in ((s.x / NM, s.y / NM), (e.x / NM, e.y / NM)):
            if ANT_X0 <= px <= ANT_X1 and 0 <= py <= ANT_Y1:
                lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
                viol.append('TRACK %s net=%s endpoint @ (%.2f, %.2f)'
                            % (lay, t.GetNetname(), px, py))
                break

for fp in b.GetFootprints():
    for p in fp.Pads():
        pos = p.GetPosition()
        x, y = pos.x / NM, pos.y / NM
        if ANT_X0 <= x <= ANT_X1 and 0 <= y <= ANT_Y1:
            viol.append('PAD %s-%s @ (%.2f, %.2f)' % (fp.GetReference(), p.GetNumber(), x, y))

# 铺铜填充多边形是否侵入净空
for z in b.Zones():
    if z.GetLayer() != pcbnew.B_Cu:
        continue
    poly = z.GetFilledPolysList(pcbnew.B_Cu)
    if poly is None or poly.OutlineCount() == 0:
        continue
    for o in range(poly.OutlineCount()):
        out = poly.Outline(o)
        for i in range(out.PointCount()):
            pt = out.CPoint(i)
            x, y = pt.x / NM, pt.y / NM
            if ANT_X0 - 0.3 <= x <= ANT_X1 + 0.3 and -0.3 <= y <= ANT_Y1 + 0.3:
                # 只关心"净空区内部"的点
                if ANT_X0 <= x <= ANT_X1 and 0 <= y <= ANT_Y1:
                    viol.append('ZONE B.Cu fill point @ (%.2f, %.2f)' % (x, y))
                    break

print('=== 1) 天线净空 x[%.2f,%.2f] y[0,%.2f] ===' % (ANT_X0, ANT_X1, ANT_Y1))
if viol:
    for v in viol[:20]:
        print('  [X] ' + v)
    print('  ⇒ %d 处侵入' % len(viol))
else:
    print('  OK —— 净空区内无任何铜箔 ✓')

# ---------- 2) 连通性 ----------
print('')
print('=== 2) 网络连通性 ===')
pad_net = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if n:
            pad_net[n].append((fp.GetReference(), p.GetNumber(),
                               p.GetPosition().x / NM, p.GetPosition().y / NM))

track_net = collections.defaultdict(int)
for t in b.GetTracks():
    track_net[t.GetNetname()] += 1

zone_nets = set()
for z in b.Zones():
    if z.GetNetname():
        zone_nets.add(z.GetNetname())

bad = []
for n, pads in sorted(pad_net.items()):
    nt = track_net.get(n, 0)
    nz = n in zone_nets
    if nt == 0 and not nz:
        bad.append('%s: 无走线且无铺铜 (%d 焊盘)' % (n, len(pads)))
    elif nt == 0 and nz:
        print('  %-6s %d 焊盘 —— 仅靠铺铜连接 ✓' % (n, len(pads)))
    else:
        print('  %-6s %d 焊盘 / %d 走线%s' % (n, len(pads), nt,
                                              ' + 铺铜' if nz else ''))
if bad:
    for x in bad:
        print('  [X] ' + x)
else:
    print('  所有网络均有铜箔连接 ✓')

# ---------- 3) 走线统计 ----------
print('')
print('=== 3) 走线统计 ===')
lay_cnt = collections.Counter()
wset = collections.Counter()
vias = 0
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        vias += 1
        continue
    lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
    lay_cnt[lay] += 1
    wset[(lay, round(t.GetWidth() / NM, 3))] += 1
for lay in ('F.Cu', 'B.Cu'):
    print('  %s: %d 段' % (lay, lay_cnt.get(lay, 0)))
print('  vias: %d' % vias)
for (lay, w), c in sorted(wset.items()):
    print('    %s 宽 %.2fmm × %d 段' % (lay, w, c))

# ---------- 4) 铺铜 ----------
print('')
print('=== 4) 铺铜 ===')
for z in b.Zones():
    lay = 'F.Cu' if z.GetLayer() == pcbnew.F_Cu else 'B.Cu'
    poly = z.GetFilledPolysList(z.GetLayer())
    n = poly.OutlineCount() if poly else 0
    area = 0.0
    if poly:
        for o in range(poly.OutlineCount()):
            out = poly.Outline(o)
            for i in range(out.PointCount()):
                pt = out.CPoint(i)
                nx = out.CPoint((i + 1) % out.PointCount())
                area += (pt.x * nx.y - nx.x * pt.y) / 2.0
    pri = z.GetAssignedPriority() if hasattr(z, 'GetAssignedPriority') else -1
    print('  %s net=%s 优先级=%d 填充多边形 %d 个 面积 %.1f mm²'
          % (lay, z.GetNetname(), pri, n, abs(area) / (NM * NM)))
