# -*- coding: utf-8 -*-
"""
upgrade_v24.py — 把已验证的 v2.3 布线板升级到 v2.4 板结构，再补 3V3

★ 为什么这么做（而不是重跑 Freerouting）
  v2.3 旧板：104 段走线，19 个网络全通，唯一未连接是 3V3 → 走线质量已收敛
  v2.4 改动只有两处，都与「走线布局」无关：
     ① 天线规则区   y[-1.00, 6.70]  →  y[-1.00, 0.80]
        （官方图纸实测：模块天线悬出 DevKit 板顶边 6.27mm，只有 0.52mm 搭进板内
          ⇒ 载板只需避开天线的**垂直投影带**，6.5mm 深度是凭空假设）
     ② GND 铺铜缺口 x[4.45,23.05] y<6.8  →  x[4.40,23.10] y<1.00
  实测重跑 Freerouting：25 个未布通项 → 剩 5 个（丢了 B1/B/LAT/SDA 4 个网络）
  ⇒ 保留 v2.3 走线，只升级板结构，是风险最低的路

★ 兼容性自检（脚本内自动跑）
  走线在 x[4.55,22.95] × y[0.80,6.70] 区域内必须为空 —— 否则升级后会撞新禁区
"""
import math

import pcbnew
from pcbnew import SHAPE_POLY_SET, VECTOR2I, ZONE

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
SRC = BASE + '/hub75-adapter-routed.v23.bak.kicad_pcb'
OUT = BASE + '/hub75-adapter-routed.kicad_pcb'

W, H = 44.0, 54.5
# v2.4 天线参数（与 gen_board.py 一致）
ANT_KO_X0, ANT_KO_X1 = 4.55, 22.95
ANT_KO_Y0, ANT_KO_Y1 = -1.0, 0.80
ANT_CU_X0, ANT_CU_X1, ANT_CU_Y1 = 4.40, 23.10, 1.00
# v2.3 旧禁区（升级后这些区域变成合法铜区，走线必须为空）
OLD_KO = (ANT_KO_X0, ANT_KO_X1, ANT_KO_Y0, 6.70)


def mm(v):
    return int(round(v * NM))


b = pcbnew.LoadBoard(SRC)
print('loaded:', SRC)
print('tracks:', len(list(b.GetTracks())))

# ============ 兼容性自检：走线不得落在 v2.3 旧禁区内 ============
bad = []
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        pts = [(t.GetPosition().x / NM, t.GetPosition().y / NM)]
    else:
        s, e = t.GetStart(), t.GetEnd()
        pts = [(s.x / NM, s.y / NM), (e.x / NM, e.y / NM)]
    for (x, y) in pts:
        if (OLD_KO[0] <= x <= OLD_KO[1]) and (OLD_KO[2] <= y <= OLD_KO[3]):
            bad.append((t.GetNetname(), x, y))
print()
print('=== 兼容性自检：走线落在 v2.3 旧禁区(6.70mm)内的段数 ===')
print('  ', len(bad))
for n, x, y in bad[:20]:
    print('    %s @ (%.2f, %.2f)' % (n, x, y))

# 焊盘也要查
for fp in b.GetFootprints():
    for p in fp.Pads():
        x, y = p.GetPosition().x / NM, p.GetPosition().y / NM
        if (OLD_KO[0] <= x <= OLD_KO[1]) and (OLD_KO[2] <= y <= OLD_KO[3]):
            print('    [pad] %s @ (%.2f, %.2f)' % (fp.GetReference() + '-' +
                                                     p.GetNumber(), x, y))

# ============ ① 天线规则区升级到 v2.4 ============
# ★ 坑：对已有的 rule area 调 SetOutline() 后再跑 ZONE_FILLER 会段错误
#   （rule area 与新 zone 的填充交互触发 C++ 断言崩溃）
#   ⇒ 改为「删掉旧 rule area → 新建一个」，与 gen_board.py 的做法一致
old_ra = None
for z in b.Zones():
    if z.GetIsRuleArea():
        old_ra = z
        break
if old_ra is None:
    raise SystemExit('rule area not found')
bb = old_ra.GetBoundingBox()
print()
print('old rule area bbox=(%.2f,%.2f)-(%.2f,%.2f)'
      % (bb.GetLeft() / NM, bb.GetTop() / NM,
         bb.GetRight() / NM, bb.GetBottom() / NM))
b.Remove(old_ra)
del old_ra
print('old rule area removed')

ant_ko = ZONE(b)
ant_ko.SetIsRuleArea(True)
ant_ko.SetDoNotAllowTracks(True)
ant_ko.SetDoNotAllowVias(True)
ant_ko.SetDoNotAllowPads(True)
ant_ko.SetDoNotAllowZoneFills(True)
ant_ko.SetDoNotAllowFootprints(True)
_ls = pcbnew.LSET()
_ls.addLayer(pcbnew.F_Cu)
_ls.addLayer(pcbnew.B_Cu)
ant_ko.SetLayerSet(_ls)
_aks = SHAPE_POLY_SET()
_aks.NewOutline()
for (x, y) in [(ANT_KO_X0, ANT_KO_Y0), (ANT_KO_X1, ANT_KO_Y0),
               (ANT_KO_X1, ANT_KO_Y1), (ANT_KO_X0, ANT_KO_Y1)]:
    _aks.Append(mm(x), mm(y))
ant_ko.SetOutline(_aks)
b.Add(ant_ko)
del ant_ko
bb = None
for z in b.Zones():
    if z.GetIsRuleArea():
        bb = z.GetBoundingBox()
        break
print('new rule area bbox=(%.2f,%.2f)-(%.2f,%.2f)'
      % (bb.GetLeft() / NM, bb.GetTop() / NM,
         bb.GetRight() / NM, bb.GetBottom() / NM))

# ============ ② GND 铺铜缺口升级到 v2.4 ============
# ★ 两个 KiCad 10 的坑（实测踩到）：
#   ① b.Remove(zone) 之后 board 的 GetNetInfo() 会退化成 SwigPyObject，
#      此时 b.GetNetsByName() 抛 AttributeError ⇒ 必须在删 zone **之前**取 net
#   ② 删 zone 后再拿 NETINFO_ITEM 指针去 SetNet() 会段错误（悬空指针）
#      ⇒ 一律改用 SetNetCode(整数 netcode)，与指针生命周期脱钩
gnd_code = b.FindNet('GND').GetNetCode()
print('GND netcode captured before zone removal:', gnd_code)

# ★ ZONE 被 b.Remove() 后若 Python 侧还持有引用，KiCad 10 会段错误。
#   ⇒ 边遍历边删，且不把 zone 存进变量列表。
removed = 0
for z in b.Zones():
    if not z.GetIsRuleArea():
        b.Remove(z)
        removed += 1
        del z
print('old copper zones removed:', removed)

z = ZONE(b)
z.SetLayer(pcbnew.B_Cu)
z.SetNetCode(gnd_code)
z.SetLocalClearance(mm(0.3))
z.SetMinThickness(mm(0.25))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetThermalReliefGap(mm(0.3))
z.SetThermalReliefSpokeWidth(mm(0.5))
ps = SHAPE_POLY_SET()
ps.NewOutline()
outline = [(0.5, 0.5), (ANT_CU_X0, 0.5), (ANT_CU_X0, ANT_CU_Y1),
           (ANT_CU_X1, ANT_CU_Y1), (ANT_CU_X1, 0.5),
           (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)]
for (x, y) in outline:
    ps.Append(mm(x), mm(y))
z.SetOutline(ps)
b.Add(z)

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
print('GND zone rebuilt (v2.4 notch) and filled')

io = pcbnew.PCB_IO_KICAD_SEXPR()
io.SaveBoard(OUT, b)
print('saved:', OUT)
