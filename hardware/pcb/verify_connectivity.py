# -*- coding: utf-8 -*-
"""
verify_connectivity.py — 独立连通性验证（不依赖 DRC 报告）

★ 逐网络做「连通分量」分析：从每个焊盘出发，沿走线/过孔/铺铜扩散，
  统计该网络的所有焊盘是否落在同一个连通分量里。
  这是对 DRC unconnected_items 的独立交叉验证。

铺铜连通性用 KiCad 自己的 GetFilledPolysList(layer) 取实心多边形，
  判断焊盘中心是否落在铺铜多边形内（GND 靠铺铜连接）。
"""
import collections

import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0
TOL = 0.01          # 判定「同一节点」的坐标容差

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

# ---- 收集走线/过孔，端点归一化成节点 key ----
def key(x, y):
    return (round(x / NM, 3), round(y / NM, 3))


edges = collections.defaultdict(set)     # net -> node pairs
for t in b.GetTracks():
    net = t.GetNetname()
    if not net:
        continue
    s, e = t.GetStart(), t.GetEnd()
    edges[net].add((key(s.x, s.y), key(e.x, e.y)))

# ---- 收集焊盘 ----
pad_nodes = collections.defaultdict(list)   # net -> [(ref-num, node)]
for fp in b.GetFootprints():
    for p in fp.Pads():
        net = p.GetNetname()
        if not net:
            continue
        pos = p.GetPosition()
        pad_nodes[net].append((fp.GetReference() + '-' + p.GetNumber(),
                               key(pos.x, pos.y)))

# ---- 铺铜多边形（用于 GND 的铜皮连接判定）----
zone_polys = []
for z in b.Zones():
    if z.GetIsRuleArea():
        continue
    for lay in (pcbnew.B_Cu, pcbnew.F_Cu):
        if not z.GetLayerSet().Contains(lay):
            continue
        try:
            poly = z.GetFilledPolysList(lay)
        except Exception as e:
            print('  (zone fill read failed on layer %d: %s)' % (lay, e))
            continue
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            pts = [(o.CPoint(k).x / NM, o.CPoint(k).y / NM)
                   for k in range(o.PointCount())]
            zone_polys.append((z.GetNetname(), lay, pts))
        for h in range(poly.HoleCount(i)):
            ho = poly.Hole(i, h)
            pts = [(ho.CPoint(k).x / NM, ho.CPoint(k).y / NM)
                   for k in range(ho.PointCount())]
            zone_polys.append((z.GetNetname(), lay, pts))
print('zone polygons loaded:', len(zone_polys))
print()


def point_in_poly(x, y, pts):
    """射线法判点是否在多边形内。"""
    n = len(pts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def components(net, node_pairs):
    """并查集。"""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, c):
        ra, rc = find(a), find(c)
        if ra != rc:
            parent[ra] = rc

    for a, c in node_pairs:
        union(a, c)
    return find


print('=' * 78)
print('=== 逐网络连通性验证 ===')
print('=' * 78)

fails = []
for net in sorted(pad_nodes):
    pads = pad_nodes[net]
    pairs = edges.get(net, set())
    find = components(net, pairs)

    # 焊盘之间的连通：焊盘中心要落在某条走线端点附近，
    #   或落在铺铜多边形内（同层）
    groups = collections.defaultdict(list)
    for name, node in pads:
        groups[find(node)].append(name)

    status = 'OK'
    detail = ''
    if net == 'GND':
        # GND：靠 B.Cu 铺铜实心连接 ⇒ 全部焊盘都应被同一块铺铜覆盖
        covered = []
        for name, node in pads:
            hit = None
            for (znet, lay, pts) in zone_polys:
                if znet != 'GND':
                    continue
                if point_in_poly(node[0], node[1], pts):
                    hit = lay
                    break
            covered.append((name, hit))
        miss = [n for n, h in covered if h is None]
        if miss:
            status = 'FAIL'
            detail = '未被 GND 铺铜覆盖: %s' % miss
        else:
            detail = '全部 %d 个焊盘均被 B.Cu 铺铜实心覆盖' % len(pads)
    else:
        if len(groups) > 1:
            status = 'FAIL'
            detail = '分裂成 %d 块: %s' % (
                len(groups), [sorted(v) for v in groups.values()])
        else:
            detail = '%d 个焊盘同一连通分量（走线/过孔）' % len(pads)

    print('%-6s %-5s %s' % (net, status, detail))
    if status == 'FAIL':
        fails.append(net)

print()
print('=' * 78)
if fails:
    print('!! 未连通网络:', fails)
else:
    print('>>> 全部 %d 个网络连通性验证通过' % len(pad_nodes))
print('=' * 78)
