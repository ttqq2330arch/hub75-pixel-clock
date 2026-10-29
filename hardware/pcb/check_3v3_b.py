# -*- coding: utf-8 -*-
"""
check_3v3_b.py — 3V3 跨 J3 排针列的**严格**几何自检（B.Cu 方案）

★ 方案要点（基于 dump_board.py 实测的全量几何）
  ① 3V3 三个焊盘全是 PTH：J1-1(2.270,1.879) / J1-2(2.270,4.419) / J4-1(27.400,5.600)
  ② J3 是 21 个 PTH 焊盘竖排在 x=25.130，缝宽仅 0.94mm
     → 只能从 J3-2/J3-3 之间穿过：缝隙 y[5.219, 6.159]，中心 5.689
  ③ **F.Cu 上是 UTX 布的墙**：
       (25.130,4.419)→(24.027,5.522) 斜线 + (24.027,5.522)→(24.027,7.456) 竖线
     → F.Cu 走缝隙#2 会被 UTX 竖线(24.027) 拦腰截断，走不了
     ⇒ 必须走 **B.Cu**（B.Cu 上 UTX 完全没有走线）
  ④ **F.Cu 没有铺铜，只有 B.Cu 有 GND 铜皮**
     → 长距离段放 F.Cu，绝不切断 GND 铜皮；只有穿缝隙那一小段下 B.Cu
     → 铺铜切断带只占 x[23.5, 28.2]，上下铜皮可从 x<23.5 宽裕绕回

★ 检测用「真·线段-线段最短距离」，不是端点距离（后者漏交叉）
"""
import math

import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0

CLEAR = 0.2          # 板最小间距 m_MinClearance
EDGE_CLEAR = 0.3     # 铜到板边
TRK_W = 0.2          # 与现有 104 段走线一致
VIA_DIA = 0.6
VIA_DRILL = 0.3
HOLE_CLEAR = 0.25    # 孔到铜

W, H = 44.0, 54.5
ANT_KO = (4.55, 22.95, -1.0, 0.80)   # 天线规则区（F.Cu+B.Cu）

# ---- 候选路径 ----
# A: F.Cu 长段 + 过孔 + B.Cu 穿缝（过孔在 y=4.419，先斜下再穿缝）
PATH_A = {
    'F.Cu': [(2.270, 4.419), (23.500, 4.419)],
    'B.Cu': [(23.500, 4.419), (24.681, 5.600), (27.400, 5.600)],
}
VIAS_A = [(23.500, 4.419)]

# B: F.Cu 长段 + 45° 斜下到 J4-1 同高(y=5.600) + 过孔 + B.Cu 水平穿缝
#    ⇒ 过孔离 J3-2 焊盘 1.42mm，穿缝段与 J3-2 净距也更大
PATH_B = {
    'F.Cu': [(2.270, 4.419), (21.719, 4.419), (22.900, 5.600)],
    'B.Cu': [(22.900, 5.600), (27.400, 5.600)],
}
VIAS_B = [(22.900, 5.600)]
TARGETS = ('J1-1', 'J1-2', 'J4-1')


def seg_seg_dist(p, q, r, s):
    ux, uy = q[0] - p[0], q[1] - p[1]
    vx, vy = s[0] - r[0], s[1] - r[1]
    wx, wy = p[0] - r[0], p[1] - r[1]
    a = ux * ux + uy * uy
    b = ux * vx + uy * vy
    c = vx * vx + vy * vy
    d = ux * wx + uy * wy
    e = vx * wx + vy * wy
    den = a * c - b * b
    if den > 1e-12:
        sc = (b * e - c * d) / den
        tc = (a * e - b * d) / den
    else:
        sc = 0.0
        tc = (e / c) if c > 1e-12 else 0.0
    sc = max(0.0, min(1.0, sc))
    tc = max(0.0, min(1.0, tc))
    dx = wx + sc * ux - tc * vx
    dy = wy + sc * uy - tc * vy
    return math.sqrt(dx * dx + dy * dy)


def point_seg_dist(pt, a, b):
    ax, ay = a
    bx, by = b
    px, py = pt
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def seg_rect_min_dist(a, b, x0, y0, x1, y1):
    best = 1e9
    n = 60
    for i in range(n + 1):
        t = i / n
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        dx = max(x0 - px, 0.0, px - x1)
        dy = max(y0 - py, 0.0, py - y1)
        best = min(best, math.hypot(dx, dy))
    return best


def pad_geom(p):
    shape = p.GetShape()
    sx, sy = p.GetSize().x / NM, p.GetSize().y / NM
    if shape == pcbnew.PAD_SHAPE_CIRCLE:
        return ('circle', 0.0, 0.0, sx / 2.0)
    if shape == pcbnew.PAD_SHAPE_OVAL:
        return ('rect', sx / 2.0, sy / 2.0, 0.0)
    return ('rect', sx / 2.0, sy / 2.0, 0.0)


def collect(b):
    """收集所有层的走线/过孔/焊盘/孔。"""
    tracks = []
    vias = []
    for t in b.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        if t.GetClass() == 'PCB_VIA':
            vias.append(dict(net=t.GetNetname(), x=s.x / NM, y=s.y / NM,
                             dia=t.GetWidth(pcbnew.F_Cu) / NM,
                             drill=t.GetDrill() / NM))
        else:
            lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
            tracks.append(dict(net=t.GetNetname(), lay=lay,
                               a=(s.x / NM, s.y / NM), b=(e.x / NM, e.y / NM),
                               w=t.GetWidth() / NM))
    pads = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            kind, hw, hh, rr = pad_geom(p)
            pos = p.GetPosition()
            dr = p.GetDrillSize().x / NM
            pads.append(dict(name=ref + '-' + p.GetNumber(), net=p.GetNetname(),
                             pos=(pos.x / NM, pos.y / NM),
                             kind=kind, hw=hw, hh=hh, r=rr, drill=dr,
                             npth=(p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)))
    return tracks, vias, pads


def check_path(name, layer_paths, vias_new, tracks, vias, pads):
    print('=' * 74)
    print('候选:', name)
    ok = True
    worst = (1e9, '')

    def note(d, what):
        nonlocal ok, worst
        if d < worst[0]:
            worst = (d, what)

    for lay, path in layer_paths.items():
        for i in range(len(path) - 1):
            a, bpt = path[i], path[i + 1]
            dx, dy = abs(bpt[0] - a[0]), abs(bpt[1] - a[1])
            tag = '%s 段%d' % (lay, i)
            # 45°/正交
            if dx > 1e-6 and dy > 1e-6 and abs(dx - dy) > 0.02:
                print('  [!] %s 非 45° (dx=%.3f dy=%.3f)' % (tag, dx, dy))
                ok = False
            # 板边
            for (px, py) in (a, bpt):
                m = min(px, py, W - px, H - py)
                if m < EDGE_CLEAR - 1e-6:
                    print('  [!] %s 端点距板边 %.3f < %.3f' % (tag, m, EDGE_CLEAR))
                    ok = False
            # 天线规则区（两层都禁）
            if not (max(a[0], bpt[0]) < ANT_KO[0] or min(a[0], bpt[0]) > ANT_KO[1] or
                    max(a[1], bpt[1]) < ANT_KO[2] or min(a[1], bpt[1]) > ANT_KO[3]):
                print('  [!] %s 进入天线规则区' % tag)
                ok = False
            # 同层走线
            for t in tracks:
                if t['lay'] != lay or t['net'] == '3V3':
                    continue
                d = seg_seg_dist(a, bpt, t['a'], t['b'])
                need = CLEAR + TRK_W / 2 + t['w'] / 2
                if d < need:
                    print('  [!] %s 距 %s 走线 (%.2f,%.2f)->(%.2f,%.2f) 仅 %.3f < %.3f'
                          % (tag, t['net'], t['a'][0], t['a'][1], t['b'][0], t['b'][1],
                             d, need))
                    ok = False
                else:
                    note(d, '%s走线 %s' % (lay, t['net']))
            # 同层过孔
            for v in vias:
                d = point_seg_dist((v['x'], v['y']), a, bpt) - v['dia'] / 2
                need = CLEAR + TRK_W / 2
                if d < need:
                    print('  [!] %s 距过孔(%.2f,%.2f) 仅 %.3f < %.3f'
                          % (tag, v['x'], v['y'], d, need))
                    ok = False
                else:
                    note(d, '过孔@(%.2f,%.2f)' % (v['x'], v['y']))
            # 焊盘（**PTH 两层都有铜**，都要查）
            for p in pads:
                if p['name'] in TARGETS:
                    continue
                if p['kind'] == 'circle':
                    d = point_seg_dist(p['pos'], a, bpt) - p['r']
                else:
                    d = seg_rect_min_dist(a, bpt, p['pos'][0] - p['hw'],
                                          p['pos'][1] - p['hh'],
                                          p['pos'][0] + p['hw'], p['pos'][1] + p['hh'])
                if p['npth']:
                    # NPTH：孔壁到铜 >= HOLE_CLEAR
                    dr = p['drill'] / 2
                    d = point_seg_dist(p['pos'], a, bpt) - dr - TRK_W / 2
                    need = HOLE_CLEAR
                    what = 'NPTH孔 %s' % p['name']
                else:
                    need = CLEAR + TRK_W / 2
                    what = '焊盘 %s' % p['name']
                if d < need:
                    print('  [!] %s 距 %s 仅 %.3f < %.3f' % (tag, what, d, need))
                    ok = False
                else:
                    note(d, what)
            print('  %s (%.3f,%.3f)->(%.3f,%.3f)  校验完成' % (tag, a[0], a[1], bpt[0], bpt[1]))

    # 新过孔检查
    for (vx, vy) in vias_new:
        # 到各层走线
        for t in tracks:
            d = point_seg_dist((vx, vy), t['a'], t['b']) - VIA_DIA / 2 - t['w'] / 2
            need = CLEAR
            if d < need:
                print('  [!] 新过孔(%.3f,%.3f) 距 %s 走线仅 %.3f < %.3f'
                      % (vx, vy, t['net'], d, need))
                ok = False
        # 到焊盘
        for p in pads:
            if p['npth']:
                d = math.hypot(vx - p['pos'][0], vy - p['pos'][1]) - p['drill'] / 2 - VIA_DRILL / 2
                need = HOLE_CLEAR
                what = 'NPTH孔 %s' % p['name']
            else:
                d = point_seg_dist(p['pos'], (vx, vy), (vx, vy)) - VIA_DIA / 2
                if p['kind'] == 'circle':
                    d -= p['r']
                else:
                    d = max(abs(vx - p['pos'][0]) - p['hw'], 0) ** 2 + \
                        max(abs(vy - p['pos'][1]) - p['hh'], 0) ** 2
                    d = math.sqrt(d) - VIA_DIA / 2
                need = CLEAR
                what = '焊盘 %s' % p['name']
            if d < need:
                print('  [!] 新过孔(%.3f,%.3f) 距 %s 仅 %.3f < %.3f'
                      % (vx, vy, what, d, need))
                ok = False
        # 孔到孔
        for p in pads:
            if p['drill'] <= 0:
                continue
            d = math.hypot(vx - p['pos'][0], vy - p['pos'][1]) - p['drill'] / 2 - VIA_DRILL / 2
            if d < HOLE_CLEAR:
                print('  [!] 新过孔(%.3f,%.3f) 孔对孔 %s 仅 %.3f < %.3f'
                      % (vx, vy, p['name'], d, HOLE_CLEAR))
                ok = False
        print('  新过孔 (%.3f,%.3f) 校验完成' % (vx, vy))

    print('  最小净距 = %.3fmm  (%s)' % (worst[0], worst[1]))
    print('  结论:', 'PASS ✓' if ok else 'FAIL ✗')
    return ok


if __name__ == '__main__':
    b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
    tracks, vias, pads = collect(b)
    print('障碍: 走线 %d, 过孔 %d, 焊盘 %d\n'
          % (len(tracks), len(vias), len(pads)))
    check_path('A_F.Cu长段+过孔+B.Cu穿缝', PATH_A, VIAS_A, tracks, vias, pads)
    print()
    check_path('B_F.Cu长段+45°斜下+过孔+B.Cu水平穿缝', PATH_B, VIAS_B, tracks, vias, pads)
