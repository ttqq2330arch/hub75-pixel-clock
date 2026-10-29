# -*- coding: utf-8 -*-
"""
step3_ses.py — 导回 SES → 重建 GND 铺铜 → 另存 routed 板

★ v2.3 修正要点：
  ① 天线铺铜轮廓方向修正：缺口必须比禁铜区**大**，不是小。
     v2.2 写 ANT_CU_X0 = ANT_X0 + 0.5（往禁铜区内缩）⇒ 铜反而铺进禁铜带。
     v2.3 与 gen_board.py 统一：ANT_CU_X0 = ANT_X0 - 0.3 = 4.45
                                ANT_CU_X1 = ANT_X1 + 0.3 = 23.05
                                ANT_CU_Y1 = ANT_Y1 + 0.3 = 6.8
  ② 只删「铜皮铺铜」，**保留天线规则区**（rule area）——
     规则区是 DRC 层面禁铜/禁走线的依据，删了天线净空就失去保护。
  ③ GND 铺铜改为 ZONE_CONNECTION_FULL（实心连接）：
     v2.2 的热焊盘连接在 J3-1(y=1.88) 处被板边切掉只剩 1 根引线，
     DRC 报「热焊盘连接不完整 + 焊盘未连上铺铜」。
     6 个 GND 焊盘全是 PTH 通孔 ⇒ 自带 B.Cu 环，实心连接直接融合，不依赖花焊盘引线。
  ④ GND 走线全部保留（Freerouting 走的那几条是合法的冗余连接路径）。
"""
import collections

import pcbnew
from pcbnew import SHAPE_POLY_SET, VECTOR2I, ZONE

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000


def mm(v):
    return int(round(v * NM))


W, H = 44.0, 54.5
# 天线规则区（与 gen_board.py 完全一致，v2.4）
# 官方图纸实测：灰色天线区 x[3.75,21.75](相对 DevKit 左缘) y[-6.27, 0.52]
#   ⇒ 模块悬出 DevKit 板顶边 6.27mm，天线在自由空间，不在载板铜箔正下方
#   ⇒ 载板只需避开天线的垂直投影带 y[0, 0.52]
ANT_KO_X0, ANT_KO_X1 = 4.55, 22.95
ANT_KO_Y0, ANT_KO_Y1 = -1.0, 0.80
# 铺铜缺口比规则区更大（各外 0.15~0.20mm）
ANT_CU_X0, ANT_CU_X1, ANT_CU_Y1 = 4.40, 23.10, 1.00

b = pcbnew.LoadBoard(BASE + '/hub75-adapter.kicad_pcb')
ok = pcbnew.ImportSpecctraSES(b, BASE + '/hub75-adapter.ses')
print('ImportSpecctraSES:', ok)
if not ok:
    raise SystemExit('SES import failed')

# ---- 只删铜皮铺铜，保留天线规则区 ----
removed = 0
for z in list(b.Zones()):
    if not z.GetIsRuleArea():
        b.Remove(z)
        removed += 1
print('copper zones removed after SES import:', removed)

# ---- 走线统计 ----
tracks = list(b.GetTracks())
by_layer = {}
gnd_tracks = []
for t in tracks:
    lay = t.GetLayer()
    by_layer[lay] = by_layer.get(lay, 0) + 1
    if t.GetNetname() == 'GND':
        gnd_tracks.append(t)
print('tracks total:', len(tracks), 'by layer:', by_layer)
print('GND tracks:', len(gnd_tracks))

# ---- 天线净空检查：任何层都不许有走线/过孔进入规则区 ----
viol = 0
for t in tracks:
    for p in (t.GetStart(), t.GetEnd()):
        x, y = p.x / NM, p.y / NM
        if (ANT_KO_X0 <= x <= ANT_KO_X1) and (ANT_KO_Y0 <= y <= ANT_KO_Y1):
            print('  [!] 走线进入天线净空: net=%s layer=%d (%.2f,%.2f)'
                  % (t.GetNetname(), t.GetLayer(), x, y))
            viol += 1
print('antenna clearance track violations:', viol)

# ---- 重建底层 GND 铺铜 ----
gnd_net = None
for ni in b.GetNetsByName().values():
    if ni.GetNetname() == 'GND':
        gnd_net = ni
        break
if gnd_net is None:
    raise SystemExit('GND net not found')

z = ZONE(b)
z.SetLayer(pcbnew.B_Cu)
z.SetNet(gnd_net)
z.SetLocalClearance(mm(0.3))
z.SetMinThickness(mm(0.25))
# ★ 实心连接：GND 焊盘直接与 B.Cu 铜皮融合，不依赖花焊盘引线
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetThermalReliefGap(mm(0.3))
z.SetThermalReliefSpokeWidth(mm(0.5))
ps = SHAPE_POLY_SET()
ps.NewOutline()
# 凹多边形：顶部中间挖出天线净空（缺口比禁铜区大 0.3mm）
for (x, y) in [(0.5, 0.5), (ANT_CU_X0, 0.5), (ANT_CU_X0, ANT_CU_Y1),
               (ANT_CU_X1, ANT_CU_Y1), (ANT_CU_X1, 0.5),
               (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]:
    ps.Append(mm(x), mm(y))
z.SetOutline(ps)
b.Add(z)

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
print('GND zone rebuilt and filled (solid connection)')

io = pcbnew.PCB_IO_KICAD_SEXPR()
io.SaveBoard(BASE + '/hub75-adapter-routed.kicad_pcb', b)
print('saved routed board')

# ---- 连通性初判 ----
pad_net = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if n:
            pad_net[n].append((fp.GetReference(), p.GetNumber(),
                               p.GetPosition().x / NM, p.GetPosition().y / NM))
unconn = []
for n, pads in sorted(pad_net.items()):
    segs = [t for t in b.GetTracks() if t.GetNetname() == n]
    if not segs:
        unconn.append((n, [p[0] + '-' + p[1] for p in pads]))
print('nets without any track:', unconn)
