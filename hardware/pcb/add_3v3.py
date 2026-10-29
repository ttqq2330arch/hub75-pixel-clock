# -*- coding: utf-8 -*-
"""
add_3v3.py — 在已布线板上补齐最后一条未连接：3V3 (J1-2 → J4-1)

★ 几何依据（check_3v3_b.py 严格自检 PASS，最小净距 0.381mm）
  ① 3V3 三个焊盘全是 PTH：J1-1(2.270,1.879) / J1-2(2.270,4.419) / J4-1(27.400,5.600)
     J1-1↔J1-2 已有 F.Cu 走线 (2.270,4.419)->(2.270,1.879)，保留
  ② 目标 J4-1 在 J3 排针列（x=25.130，21 个 PTH）东侧 ⇒ 必须横穿 J3
     唯一可穿缝隙 = J3-2(4.419) 与 J3-3(6.959) 之间，y∈[5.219,6.159]
  ③ F.Cu 上是 UTX 布的墙：
       (25.130,4.419)→(24.027,5.522) 斜线 + (24.027,5.522)→(24.027,7.456) 竖线
     ⇒ F.Cu 穿缝会被 UTX 竖线截断，走不通
     ⇒ 穿缝段必须走 **B.Cu**（B.Cu 上 UTX 完全无走线）
  ④ **F.Cu 无铺铜，只有 B.Cu 有 GND 铜皮**
     ⇒ 长距离段放 F.Cu（不切断铜皮）；B.Cu 只用 x∈[22.9,27.4] 一小段
     ⇒ 上下铜皮可从 x<22.9 宽裕绕回，GND 连通不受影响

★ 最终路径
  F.Cu: (2.270,4.419) ──水平──> (21.719,4.419) ──45°──> (22.900,5.600)
  过孔: (22.900,5.600)   dia 0.60 / drill 0.30
  B.Cu: (22.900,5.600) ──水平穿 J3 缝隙──> (27.400,5.600) = J4-1 焊盘中心
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000


def mm(v):
    return int(round(v * NM))


b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')

net = None
for ni in b.GetNetsByName().values():
    if ni.GetNetname() == '3V3':
        net = ni
        break
if net is None:
    raise SystemExit('net 3V3 not found')

# ---- 清理：删掉已有的 3V3 走线（保留 J1-1↔J1-2 那段）----
removed = 0
for t in list(b.GetTracks()):
    if t.GetNetname() == '3V3':
        s, e = t.GetStart(), t.GetEnd()
        # 保留垂直段 (2.270,4.419)->(2.270,1.879)
        if (abs(s.x - e.x) < 1000 and abs(s.x / NM - 2.270) < 0.01):
            continue
        b.Remove(t)
        removed += 1
print('removed 3V3 tracks (except J1-1<->J1-2):', removed)

TRK_W = mm(0.2)


def add_track(layer, x1, y1, x2, y2):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    t.SetWidth(TRK_W)
    t.SetLayer(layer)
    t.SetNet(net)
    b.Add(t)
    return t


# ---- F.Cu 长段 ----
add_track(pcbnew.F_Cu, 2.270, 4.419, 21.719, 4.419)
add_track(pcbnew.F_Cu, 21.719, 4.419, 22.900, 5.600)

# ---- 过孔 (22.900, 5.600) ----
v = pcbnew.PCB_VIA(b)
v.SetPosition(pcbnew.VECTOR2I(mm(22.900), mm(5.600)))
v.SetWidth(mm(0.60))
v.SetDrill(mm(0.30))
v.SetViaType(pcbnew.VIATYPE_THROUGH)
v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
v.SetNet(net)
b.Add(v)

# ---- B.Cu 穿缝段 ----
add_track(pcbnew.B_Cu, 22.900, 5.600, 27.400, 5.600)

# ---- 重新填充铜皮（让 B.Cu 铜皮给新走线让位）----
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
print('zones refilled')

io = pcbnew.PCB_IO_KICAD_SEXPR()
io.SaveBoard(BASE + '/hub75-adapter-routed.kicad_pcb', b)
print('saved routed board with 3V3 completed')

# ---- 统计 ----
tr = list(b.GetTracks())
print('tracks total:', len(tr))
for t in tr:
    if t.GetNetname() == '3V3':
        if t.GetClass() == 'PCB_VIA':
            print('  3V3 VIA  (%.3f, %.3f)'
                  % (t.GetPosition().x / NM, t.GetPosition().y / NM))
        else:
            lay = 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu'
            s, e = t.GetStart(), t.GetEnd()
            print('  3V3 TRK  %s (%.3f,%.3f)->(%.3f,%.3f)'
                  % (lay, s.x / NM, s.y / NM, e.x / NM, e.y / NM))
