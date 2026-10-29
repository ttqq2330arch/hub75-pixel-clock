# -*- coding: utf-8 -*-
"""probe_ant.py — 精确检查天线净空：走线做「线段∩矩形」相交测试（而非只测端点），
并输出 J3-1 附近（GND 花焊盘）区域的几何细节。"""
import sys
import pcbnew

NM = 1_000_000
PCB = sys.argv[1] if len(sys.argv) > 1 else \
    r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter-routed.kicad_pcb'

ANT_X0, ANT_X1, ANT_Y1 = 4.75, 22.75, 6.5


def seg_rect_hit(x1, y1, x2, y2, x0, y0, x1b, y1b):
    """线段与矩形是否相交（含端点在内）"""
    def inside(x, y):
        return x0 <= x <= x1b and y0 <= y <= y1b
    if inside(x1, y1) or inside(x2, y2):
        return True
    # 与四条边求交
    edges = [(x0, y0, x1b, y0), (x1b, y0, x1b, y1b),
             (x1b, y1b, x0, y1b), (x0, y1b, x0, y0)]
    for (ax, ay, bx, by) in edges:
        d1 = (x2 - x1) * (ay - y1) - (y2 - y1) * (ax - x1)
        d2 = (x2 - x1) * (by - y1) - (y2 - y1) * (bx - x1)
        d3 = (bx - ax) * (y1 - ay) - (by - ay) * (ax - x1)
        d4 = (bx - ax) * (y2 - ay) - (by - ay) * (ax - x1)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


b = pcbnew.LoadBoard(PCB)
print('board:', PCB)
print('')
print('=== 1) 走线穿越天线净空（线段∩矩形 精确判定）===')
hits = []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        p = t.GetPosition()
        x, y = p.x / NM, p.y / NM
        if ANT_X0 <= x <= ANT_X1 and 0 <= y <= ANT_Y1:
            hits.append('VIA @ (%.2f,%.2f) net=%s' % (x, y, t.GetNetname()))
        continue
    s, e = t.GetStart(), t.GetEnd()
    x1, y1 = s.x / NM, s.y / NM
    x2, y2 = e.x / NM, e.y / NM
    if seg_rect_hit(x1, y1, x2, y2, ANT_X0, 0.0, ANT_X1, ANT_Y1):
        lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
        hits.append('TRACK %s net=%s (%.2f,%.2f)->(%.2f,%.2f)'
                    % (lay, t.GetNetname(), x1, y1, x2, y2))
if hits:
    for h in hits:
        print('  [X] ' + h)
    print('  ⇒ %d 条走线穿越净空' % len(hits))
else:
    print('  OK —— 无走线穿越净空 ✓')

print('')
print('=== 2) 铺铜填充多边形侵入净空（逐点 + 逐边）===')
zhit = 0
for z in b.Zones():
    if z.GetLayer() != pcbnew.B_Cu:
        continue
    poly = z.GetFilledPolysList(pcbnew.B_Cu)
    if poly is None:
        continue
    for o in range(poly.OutlineCount()):
        out = poly.Outline(o)
        n = out.PointCount()
        pts = [(out.CPoint(i).x / NM, out.CPoint(i).y / NM) for i in range(n)]
        for i in range(n):
            x, y = pts[i]
            if ANT_X0 <= x <= ANT_X1 and 0 <= y <= ANT_Y1:
                print('  [X] 顶点 (%.3f,%.3f)' % (x, y))
                zhit += 1
                break
        else:
            # 顶点都在外面，但可能有边穿过
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                if seg_rect_hit(x1, y1, x2, y2, ANT_X0, 0.0, ANT_X1, ANT_Y1):
                    print('  [X] 边 (%.3f,%.3f)->(%.3f,%.3f) 穿过' % (x1, y1, x2, y2))
                    zhit += 1
                    break
if zhit == 0:
    print('  OK —— 铺铜未侵入净空 ✓')
else:
    print('  ⇒ %d 处侵入' % zhit)

print('')
print('=== 3) J3-1 (GND 花焊盘) 周边 x[22,29] y[0,6] ===')
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    x1, y1 = s.x / NM, s.y / NM
    x2, y2 = e.x / NM, e.y / NM
    if 21 <= min(x1, x2) and max(x1, x2) <= 30 and min(y1, y2) <= 6 and max(y1, y2) <= 6:
        lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
        print('  TRACK %-5s net=%-4s (%.2f,%.2f)->(%.2f,%.2f) w=%.2f'
              % (lay, t.GetNetname(), x1, y1, x2, y2, t.GetWidth() / NM))

print('')
print('=== 4) GND 网络走线清单 ===')
for t in b.GetTracks():
    if t.GetNetname() == 'GND':
        lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
        s, e = t.GetStart(), t.GetEnd()
        print('  %-5s (%.2f,%.2f)->(%.2f,%.2f)'
              % (lay, s.x / NM, s.y / NM, e.x / NM, e.y / NM))
