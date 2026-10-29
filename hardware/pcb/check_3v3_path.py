# -*- coding: utf-8 -*-
"""
check_3v3_path.py — 3V3 手工走线的**严格**几何自检

★ 为什么不用 plan_3v3_f.py：
  plan_3v3_f.py 的碰撞检测用的是「我这段的**端点**到对方线段的距离」，
  这会漏掉**交叉**的情况 —— 两段垂直交叉时端点距离可能是 1mm，实际距离是 0。
  本脚本用真正的「线段-线段」最短距离。

★ 为什么不用 Freerouting 预布线：
  已查明 DSN 坐标单位是 1/1000 mm（板宽 44000 = 44mm），不是 1/10000；
  语法是扁平单行 (wire (path 层 宽 x1 y1 x2 y2 ...)(net 名)(type route))。
  之前两处都错 ⇒ 整条线被放大 10 倍扔到板外，Freerouting 直接丢弃。
  但即便改对格式，Freerouting 是否保留预布线仍不可控
  ⇒ 改为「Freerouting 布完其余网络 → 手工补 3V3 → 官方 DRC 判定」，
     判定权交给 KiCad 官方 DRC，不靠推断。

坐标：KiCad 原生，Y 向下为正。
"""
import math

import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0

CLEAR = 0.2        # 板最小间距 (m_MinClearance)
EDGE_CLEAR = 0.3   # 铜到板边
TRK_W = 0.2        # 与现有走线一致的线宽（实测全部 104 段都是 0.2mm）
PAD_HALF_DIAG = 1.6 / 2 * math.sqrt(2)   # 1.6mm 方形焊盘半对角（保守按圆算）

W, H = 44.0, 54.5
ANT_KO = (4.55, 22.95, -1.0, 0.80)      # 天线规则区（与 gen_board.py 一致）

# 候选路径：J1-1 → J1-2 → 绕行 → J4-1，全程 45°/正交，无 T 型接头
CANDIDATES = {
    'A_detour_x330': [
        (2.27, 1.879),    # J1-1
        (2.27, 4.419),    # J1-2（竖直穿过，两脚都连上）
        (3.30, 4.419),    # 向右让开 J1 焊盘列
        (3.30, 3.15),     # 上折到水平车道
        (26.10, 3.15),    # 水平穿过 J3 缝隙#0（y 2.68..3.62）
        (26.95, 4.00),    # 45° 斜下
        (27.40, 4.45),    # 45° 斜下
        (27.40, 5.60),    # J4-1
    ],
    'B_detour_x380': [
        (2.27, 1.879),
        (2.27, 4.419),
        (3.80, 4.419),
        (3.80, 3.15),
        (26.10, 3.15),
        (26.95, 4.00),
        (27.40, 4.45),
        (27.40, 5.60),
    ],
}


def seg_seg_dist(p, q, r, s):
    """两线段最短距离（2D）。"""
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
    # 夹紧后再投影一次，得到真正最近点
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
    """线段到轴对齐矩形的最短距离（采样足够密 + 端点投影）。"""
    best = 1e9
    n = 40
    for i in range(n + 1):
        t = i / n
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        dx = max(x0 - px, 0.0, px - x1)
        dy = max(y0 - py, 0.0, py - y1)
        best = min(best, math.hypot(dx, dy))
    return best


def pad_geom(p):
    """返回焊盘的 (kind, 半宽, 半高, 半径)。KiCad PAD_SHAPE: 0=CIRCLE 1=RECT 2=OVAL"""
    shape = p.GetShape()
    sx, sy = p.GetSize().x / NM, p.GetSize().y / NM
    if shape == pcbnew.PAD_SHAPE_CIRCLE:
        return ('circle', 0.0, 0.0, sx / 2.0)
    if shape == pcbnew.PAD_SHAPE_OVAL:
        return ('rect', sx / 2.0, sy / 2.0, 0.0)
    return ('rect', sx / 2.0, sy / 2.0, 0.0)


def load_board():
    b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
    return b


def collect(b):
    """收集 F.Cu 上的走线（排除 3V3，它会被替换）和所有焊盘。"""
    segs = []
    for t in b.GetTracks():
        if t.GetLayer() != pcbnew.F_Cu:
            continue
        if t.GetNetname() == '3V3':
            continue
        if t.GetClass() == 'PCB_VIA':
            # ★ PCB_VIA.GetWidth() 不带 layer 参数会触发 C++ assert（进程被打断）
            #   ⇒ 必须传 pcbnew.F_Cu
            r = t.GetWidth(pcbnew.F_Cu) / NM / 2
            s = t.GetStart()
            segs.append(('via', (s.x / NM, s.y / NM), r))
        else:
            s, e = t.GetStart(), t.GetEnd()
            segs.append(('track', (s.x / NM, s.y / NM), (e.x / NM, e.y / NM),
                         t.GetWidth() / NM))
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            kind, hw, hh, rr = pad_geom(p)
            cx, cy = p.GetPosition().x / NM, p.GetPosition().y / NM
            pads.append((fp.GetReference() + '-' + p.GetNumber(),
                         p.GetNetname(), (cx, cy),
                         (kind, hw, hh, rr)))
    return segs, pads


TARGETS = ('J1-1', 'J1-2', 'J4-1')


def check(name, path, segs, pads):
    print('=' * 72)
    print('候选:', name)
    ok = True
    worst = 1e9
    worst_what = ''

    for i in range(len(path) - 1):
        a, bpt = path[i], path[i + 1]
        dx, dy = abs(bpt[0] - a[0]), abs(bpt[1] - a[1])
        # 1) 45°/正交规范
        if dx > 1e-6 and dy > 1e-6 and abs(dx - dy) > 0.02:
            print('  [!] 段%d 非 45° (dx=%.2f dy=%.2f)' % (i, dx, dy))
            ok = False
        # 2) 板边
        for (px, py) in (a, bpt):
            m = min(px, py, W - px, H - py)
            if m < EDGE_CLEAR - 1e-6:
                print('  [!] 段%d 端点距板边 %.3f < %.3f' % (i, m, EDGE_CLEAR))
                ok = False
        # 3) 天线规则区
        if not (max(a[0], bpt[0]) < ANT_KO[0] or min(a[0], bpt[0]) > ANT_KO[1] or
                max(a[1], bpt[1]) < ANT_KO[2] or min(a[1], bpt[1]) > ANT_KO[3]):
            print('  [!] 段%d 进入天线规则区' % i)
            ok = False
        # 4) 与已有 F.Cu 走线（真·线段距离）
        for s in segs:
            if s[0] == 'via':
                d = point_seg_dist(s[1], a, bpt) - s[2]
                need = CLEAR + TRK_W / 2
                if d < need:
                    print('  [!] 段%d 距过孔 (%.2f,%.2f) 仅 %.3f < %.3f'
                          % (i, s[1][0], s[1][1], d, need))
                    ok = False
                elif d < worst:
                    worst, worst_what = d, 'via@(%.2f,%.2f)' % s[1]
            else:
                d = seg_seg_dist(a, bpt, s[1], s[2])
                need = CLEAR + TRK_W / 2 + s[3] / 2
                if d < need:
                    print('  [!] 段%d 距走线 (%.2f,%.2f)->(%.2f,%.2f) 仅 %.3f < %.3f'
                          % (i, s[1][0], s[1][1], s[2][0], s[2][1], d, need))
                    ok = False
                elif d < worst:
                    worst, worst_what = d, 'track(%.2f,%.2f)->(%.2f,%.2f)' % (
                        s[1][0], s[1][1], s[2][0], s[2][1])
        # 5) 与焊盘（目标焊盘除外）
        for nm, net, pos, (kind, hw, hh, rr) in pads:
            if nm in TARGETS:
                continue
            if kind == 'circle':
                d = point_seg_dist(pos, a, bpt) - rr
            else:
                d = seg_rect_min_dist(a, bpt, pos[0] - hw, pos[1] - hh,
                                      pos[0] + hw, pos[1] + hh)
            need = CLEAR + TRK_W / 2
            if d < need:
                print('  [!] 段%d 距焊盘 %s (%.2f,%.2f) 仅 %.3f < %.3f'
                      % (i, nm, pos[0], pos[1], d, need))
                ok = False
            elif d < worst:
                worst, worst_what = d, 'pad ' + nm
        print('  段%d (%.2f,%.2f)->(%.2f,%.2f)  OK'
              % (i, a[0], a[1], bpt[0], bpt[1]))

    print('  最小净距 = %.3fmm  (%s)' % (worst, worst_what))
    print('  结论:', 'PASS ✓' if ok else 'FAIL ✗')
    return ok


if __name__ == '__main__':
    b = load_board()
    segs, pads = collect(b)
    print('F.Cu 障碍(走线+过孔) %d 条, 焊盘 %d 个\n' % (len(segs), len(pads)))
    results = {}
    for name, path in CANDIDATES.items():
        results[name] = check(name, path, segs, pads)
        print()
    print('=' * 72)
    for k, v in results.items():
        print('%-16s %s' % (k, 'PASS' if v else 'FAIL'))
