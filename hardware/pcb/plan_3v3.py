# -*- coding: utf-8 -*-
"""
plan_3v3.py — 为 3V3 规划一条手工走线（预布线，注入 DSN 的 wiring 段）

问题：3V3 需从 J1-2 (2.27, 4.42) 连到 J4-1 (27.40, 5.60)。
      F.Cu 上被 J3 排针列 + UTX/URX 走线堵死；Freerouting 两次都放弃。
      但 B.Cu 在 y≈5.60 一线是干净的（实测只有 SCL 从上方斜下来）。
      ⇒ 手工规划一条 B.Cu 路径，作为「已完成走线」注入 DSN，
        Freerouting 便只需把它连到 J4-1 即可。

坐标约定：DSN/SES 用 1/10 µm 为单位（resolution um 10 → 实际 0.1µm）
  实测：22700 = 2.27mm  ⇒ 单位 = 1/10000 mm
  Y 轴向上为正（KiCad 向下为正），故 KiCad y = -DSN y
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
D = 10_000          # DSN/SES 坐标单位 / mm


def to_dsn(x, y):
    """KiCad mm → DSN 单位（Y 取反）"""
    return (int(round(x * D)), int(round(-y * D)))


# ---- 路径点（KiCad 坐标 mm）----
# ① J1-2 (2.27, 4.42) 斜 45° 下行到 (3.45, 5.60)
# ② 水平直行到 J4-1 (27.40, 5.60)
PATH = [
    (2.27, 4.42),
    (3.45, 5.60),
    (27.40, 5.60),
]

print('=== 3V3 手工路径 ===')
for i, (x, y) in enumerate(PATH):
    print('  P%d (%.2f, %.2f)' % (i, x, y))

# ---- 逐段做几何自检 ----
b = pcbnew.LoadBoard(BASE + '/hub75-adapter.kicad_pcb')
CLEAR = 0.2
TRK_W = 0.3          # 本次手工走线用 0.3mm（电源线加粗）

segs = []
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    w = 0.8 if t.GetClass() == 'PCB_VIA' else t.GetWidth() / NM
    segs.append((t.GetNetname(), t.GetLayer(), s.x / NM, s.y / NM, e.x / NM, e.y / NM, w))


def seg_dist(px, py, x1, y1, x2, y2):
    """点到线段的最短距离"""
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    qx, qy = x1 + t * dx, y1 + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


print()
print('=== 与已有走线的间距自检（走线按 0.3mm）===')
worst = (999, None)
for i in range(len(PATH) - 1):
    (x1, y1), (x2, y2) = PATH[i], PATH[i + 1]
    for (net, lay, ax, ay, bx, by, w) in segs:
        if lay != pcbnew.B_Cu:
            continue
        if net == '3V3':
            continue
        # 只检查与本段包围盒有交集的
        if max(x1, x2) < min(ax, bx) - 1 or min(x1, x2) > max(ax, bx) + 1:
            continue
        if max(y1, y2) < min(ay, by) - 1 or min(y1, y2) > max(ay, by) + 1:
            continue
        d = seg_dist(x1, y1, ax, ay, bx, by)
        d2 = seg_dist(x2, y2, ax, ay, bx, by)
        d = min(d, d2)
        need = CLEAR + TRK_W / 2 + w / 2
        if d < worst[0]:
            worst = (d, (net, ax, ay, bx, by, lay))
        if d < need:
            print('  [!] 段%d 与 %s (layer%d) 距离 %.3fmm < 需要 %.3fmm'
                  % (i, net, lay, d, need))
print('  最小间距: %.3fmm  (%s)' % (worst[0], worst[1]))

print()
print('=== 与焊盘的间距自检 ===')
for i in range(len(PATH) - 1):
    (x1, y1), (x2, y2) = PATH[i], PATH[i + 1]
    for fp in b.GetFootprints():
        for p in fp.Pads():
            px, py = p.GetPosition().x / NM, p.GetPosition().y / NM
            d = seg_dist(px, py, x1, y1, x2, y2)
            need = CLEAR + TRK_W / 2 + 0.8
            if d < need:
                same = (fp.GetReference() + '-' + p.GetNumber() == 'J1-2')
                tag = ' (同网络, 起点)' if same else ''
                if not same:
                    print('  [!] 段%d 距 %s-%s (%.2f,%.2f) 仅 %.3fmm < %.3f'
                          % (i, fp.GetReference(), p.GetNumber(), px, py, d, need))

print()
print('=== 注入用的 DSN 片段 ===')
pts = ' '.join('%d %d' % to_dsn(x, y) for (x, y) in PATH)
frag = ('  (wiring\n'
        '    (net 3V3\n'
        '      (wire\n'
        '        (path B.Cu 3000\n'
        '          %s\n'
        '        )\n'
        '      )\n'
        '    )\n'
        '  )' % pts)
print(frag)
open(BASE + '/_wiring_3v3.txt', 'w', encoding='utf-8').write(frag)
print()
print('已写入 _wiring_3v3.txt')
