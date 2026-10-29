# -*- coding: utf-8 -*-
"""
dump_board.py — 全量导出 routed 板的真实几何（焊盘 / 走线 / 过孔 / 规则区）

坐标：KiCad 原生 mm，Y 向下为正。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0

SHAPE = {0: 'CIRCLE', 1: 'RECT', 2: 'OVAL', 3: 'TRAPEZOID', 4: 'ROUNDRECT'}
ATTR = {0: 'PTH', 1: 'SMD', 2: 'CONN', 3: 'NPTH'}

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

print('=== 焊盘 ===')
pads = []
for fp in b.GetFootprints():
    ref = fp.GetReference()
    print('  [%s] %s  (%.2f, %.2f)' % (ref, fp.GetValue(),
                                        fp.GetPosition().x / NM, fp.GetPosition().y / NM))
    for p in fp.Pads():
        pos = p.GetPosition()
        sz = p.GetSize()
        dr = p.GetDrillSize()
        shape = SHAPE.get(p.GetShape(), str(p.GetShape()))
        attr = ATTR.get(p.GetAttribute(), str(p.GetAttribute()))
        rot = p.GetOrientationDegrees()
        lay = 'PTH' if p.GetAttribute() in (0, 2) else 'SMD'
        info = dict(ref=ref, num=p.GetNumber(), net=p.GetNetname(),
                    x=pos.x / NM, y=pos.y / NM,
                    sx=sz.x / NM, sy=sz.y / NM,
                    dr=dr.x / NM, shape=shape, rot=rot, attr=attr)
        pads.append(info)
        print('    -%-3s net=%-5s (%7.3f,%7.3f) size=%.2fx%.2f %-9s drill=%.2f rot=%.0f'
              % (p.GetNumber(), p.GetNetname() or '-', info['x'], info['y'],
                 info['sx'], info['sy'], shape, info['dr'], rot))

print()
print('=== 走线 / 过孔 ===')
tracks = []
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else (
        'B.Cu' if t.GetLayer() == pcbnew.B_Cu else 'L%d' % t.GetLayer())
    if t.GetClass() == 'PCB_VIA':
        tracks.append(dict(kind='via', net=t.GetNetname(), lay='VIA',
                           x1=s.x / NM, y1=s.y / NM, x2=e.x / NM, y2=e.y / NM,
                           w=t.GetWidth(pcbnew.F_Cu) / NM, dr=t.GetDrill() / NM))
        print('  VIA   %-5s (%7.3f,%7.3f)  dia=%.2f drill=%.2f'
              % (t.GetNetname(), s.x / NM, s.y / NM,
                 t.GetWidth(pcbnew.F_Cu) / NM, t.GetDrill() / NM))
    else:
        tracks.append(dict(kind='track', net=t.GetNetname(), lay=lay,
                           x1=s.x / NM, y1=s.y / NM, x2=e.x / NM, y2=e.y / NM,
                           w=t.GetWidth() / NM, dr=0.0))
        print('  TRK   %-5s %-4s (%7.3f,%7.3f)->(%7.3f,%7.3f) w=%.2f'
              % (t.GetNetname(), lay, s.x / NM, s.y / NM, e.x / NM, e.y / NM,
                 t.GetWidth() / NM))

print()
print('=== B.Cu 走线清单（3V3 规划要避让的）===')
for t in tracks:
    if t['lay'] == 'B.Cu':
        print('  %-5s (%7.3f,%7.3f)->(%7.3f,%7.3f) w=%.2f'
              % (t['net'], t['x1'], t['y1'], t['x2'], t['y2'], t['w']))

print()
print('=== 规则区 (rule area) ===')
for z in b.Zones():
    if z.GetIsRuleArea():
        bbox = z.GetBoundingBox()
        layers = z.GetLayerSet().FmtHex()
        print('  rule area: layers=%s bbox=(%.2f,%.2f)-(%.2f,%.2f)'
              % (layers, bbox.GetLeft() / NM, bbox.GetTop() / NM,
                 bbox.GetRight() / NM, bbox.GetBottom() / NM))
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.GetLayerSet().Contains(lay):
                poly = z.GetPolysList(lay)
                for i in range(poly.OutlineCount()):
                    o = poly.Outline(i)
                    pts = [(o.CPoint(k).x / NM, o.CPoint(k).y / NM)
                           for k in range(o.PointCount())]
                    print('    %s outline: %s' % ('F.Cu' if lay == pcbnew.F_Cu
                                                  else 'B.Cu', pts))

print()
print('=== 铺铜区 ===')
for z in b.Zones():
    if not z.GetIsRuleArea():
        bbox = z.GetBoundingBox()
        print('  zone: net=%s layers=%s bbox=(%.2f,%.2f)-(%.2f,%.2f)'
              % (z.GetNetname(), z.GetLayerSet().FmtHex(),
                 bbox.GetLeft() / NM, bbox.GetTop() / NM,
                 bbox.GetRight() / NM, bbox.GetBottom() / NM))
