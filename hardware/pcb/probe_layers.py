# probe_layers.py — 查清 KiCad 10 层号常量与实际走线归属
import pcbnew
from collections import defaultdict

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000

print('F_Cu =', pcbnew.F_Cu, ' B_Cu =', pcbnew.B_Cu)
for name in ('F_Cu', 'In1_Cu', 'B_Cu', 'In2_Cu'):
    v = getattr(pcbnew, name, None)
    if v is not None:
        print('  const %-6s = %d' % (name, v))

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

print('\n=== 走线按 (层, 网络) 统计 ===')
agg = defaultdict(int)
vias = defaultdict(int)
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        vias[t.GetLayer()] += 1
    else:
        agg[(t.GetLayer(), t.GetNetname())] += 1
for lay in sorted(set([k[0] for k in agg])):
    items = [(k[1], v) for k, v in agg.items() if k[0] == lay]
    items.sort()
    print('layer %d :' % lay)
    for n, v in items:
        print('    %-6s %d 段' % (n, v))
print('vias:', dict(vias))

print('\n=== 网络 -> 焊盘数 ===')
padc = defaultdict(int)
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if n:
            padc[n] += 1
for n, c in sorted(padc.items()):
    print('  %-6s %d' % (n, c))

print('\n=== 铺铜区 ===')
for z in b.Zones():
    print('  layer=%d net=%s priority=%s' % (z.GetLayer(), z.GetNetname(), z.GetAssignedPriority()))
    poly = z.GetFilledPolysList(pcbnew.B_Cu if z.GetLayer() == pcbnew.B_Cu else pcbnew.F_Cu)
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        pts = [(p.x / NM, p.y / NM) for p in o.CPoints()]
        print('    outline %d: %d 点, x[%.2f,%.2f] y[%.2f,%.2f]' % (
            i, len(pts), min(p[0] for p in pts), max(p[0] for p in pts),
            min(p[1] for p in pts), max(p[1] for p in pts)))
        # 净空区附近的点
        near = [p for p in pts if p[1] < 7.5 and 3.5 < p[0] < 24.0]
        print('    净空区附近点:', sorted(set([('%.3f,%.3f' % p) for p in near])))
