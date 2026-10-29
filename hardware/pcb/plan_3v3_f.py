# -*- coding: utf-8 -*-
"""
plan_3v3_f.py — 为 3V3 规划一条 **F.Cu** 手工路径（不破坏 B.Cu 的 GND 平面）

约束：
  · 起点 J1-2 (2.27, 4.42) —— 3V3 在 J1 上有两个脚 J1-1(2.27,1.88) / J1-2(2.27,4.42)
  · 终点 J4-1 (27.40, 5.60)
  · 必须横穿 J3 通孔焊盘列 (x=25.13, 贯穿全高) ⇒ 只能走「缝隙 #0」(y 2.68..3.62)
  · 必须避让 UTX 走线（实测占据 y 4.42..9.07, x 24.03..26.30）
  · 必须避让 J3-1 (25.13,1.88) 与 J3-2 (25.13,4.42)
  · 天线规则区 x[4.55,22.95] y[-1,0.80] 不得进入

方案：
  J1-2 (2.27,4.42) ─斜上→ (2.27,3.15) 区段 ─水平→ (24.0,3.15) ─过缝隙#0→ (26.2,3.15)
      ─斜下→ J4-1 (27.40,5.60)
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
CLEAR = 0.2
TRK_W = 0.3

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

# ---- 候选路径 ----
PATH = [
    (2.27, 4.42),     # J1-2
    (2.27, 3.15),     # 竖直上行到车道
    (24.00, 3.15),    # 水平走到 J3 列左侧
    (26.10, 3.15),    # 水平穿过 J3 缝隙#0 (y 2.68..3.62)
    (26.95, 4.00),    # 45° 斜下拐点
    (27.40, 4.45),    # 45° 斜下终点
    (27.40, 5.60),    # 竖直下行到 J4-1
]


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    qx, qy = x1 + t * dx, y1 + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def bbox_hit(x1, y1, x2, y2, ax, ay, bx, by, pad=1.0):
    return not (max(x1, x2) < min(ax, bx) - pad or
                min(x1, x2) > max(ax, bx) + pad or
                max(y1, y2) < min(ay, by) - pad or
                min(y1, y2) > max(ay, by) + pad)


print('=== 路径 ===')
for i, (x, y) in enumerate(PATH):
    print('  P%d (%.2f, %.2f)' % (i, x, y))

print()
print('=== 逐段自检 ===')
ok = True
for i in range(len(PATH) - 1):
    (x1, y1), (x2, y2) = PATH[i], PATH[i + 1]
    seglen = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

    # 1) 45° 规范（斜段必须 45°）
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    if dx > 0.01 and dy > 0.01 and abs(dx - dy) > 0.02:
        print('  [!] 段%d 不是 45° (dx=%.2f dy=%.2f)' % (i, dx, dy))
        ok = False

    # 2) 与已有走线
    for t in b.GetTracks():
        if t.GetLayer() != pcbnew.F_Cu:
            continue
        if t.GetNetname() == '3V3':
            continue
        s, e = t.GetStart(), t.GetEnd()
        ax, ay, bx, by = s.x / NM, s.y / NM, e.x / NM, e.y / NM
        if not bbox_hit(x1, y1, x2, y2, ax, ay, bx, by):
            continue
        w = 0.8 if t.GetClass() == 'PCB_VIA' else t.GetWidth() / NM
        d = min(seg_dist(x1, y1, ax, ay, bx, by), seg_dist(x2, y2, ax, ay, bx, by))
        need = CLEAR + TRK_W / 2 + w / 2
        if d < need:
            print('  [!] 段%d 距 %s (%.2f,%.2f)->(%.2f,%.2f) 仅 %.3f < %.3f'
                  % (i, t.GetNetname(), ax, ay, bx, by, d, need))
            ok = False

    # 3) 与焊盘
    for fp in b.GetFootprints():
        for p in fp.Pads():
            px, py = p.GetPosition().x / NM, p.GetPosition().y / NM
            nm = fp.GetReference() + '-' + p.GetNumber()
            if nm in ('J1-2', 'J4-1'):
                continue
            d = seg_dist(px, py, x1, y1, x2, y2)
            need = CLEAR + TRK_W / 2 + 0.8
            if d < need:
                print('  [!] 段%d 距 %s (%.2f,%.2f) 仅 %.3f < %.3f'
                      % (i, nm, px, py, d, need))
                ok = False

    # 4) 天线规则区
    ANT = (4.55, 22.95, -1.0, 0.80)
    if not (max(x1, x2) < ANT[0] or min(x1, x2) > ANT[1] or
            max(y1, y2) < ANT[2] or min(y1, y2) > ANT[3]):
        print('  [!] 段%d 进入天线规则区' % i)
        ok = False

    print('  段%d (%.2f,%.2f)->(%.2f,%.2f)  长 %.2fmm  检查完成'
          % (i, x1, y1, x2, y2, seglen))

print()
print('结论:', 'PASS ✓' if ok else 'FAIL ✗')
