# -*- coding: utf-8 -*-
"""
analyze_barrier.py — 摸清 J3 通孔焊盘列这道「墙」的真实几何

★ 背景
  J3 是 22P 排母的**右列**，21 个 PTH 焊盘在 x=25.13 竖排贯穿全高。
  板上任何从西侧(x<25)到东侧(x>26)的连接都必须**穿过 J3 焊盘之间的缝隙**。
  J3 相邻焊盘间距 2.54、焊盘 1.6 ⇒ 缝宽仅 0.94mm。

★ 要回答的三个问题
  Q1 哪些缝隙已被走线占用？（含 F.Cu / B.Cu 两层）
  Q2 J3 与东侧器件(J4/J5/J2)之间的「窄沟」(x≈25.93..26.60) 是否被占？
  Q3 窄沟在 y 方向上被什么挡住？（安装孔 H1/H3 的孔径 vs 铜间距）

★ 输出直接决定 3V3 的走法。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0

J3_X = 25.13
J3_PAD_HALF = 0.8
J3_Y0 = 1.879
PITCH = 2.54
NPIN = 21

# 东侧器件左缘
J4_X0 = 27.40
J5_X0 = 27.40
J2_XL = 27.90
EAST_EDGE = J4_X0 - 0.8      # 26.60

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
ds = b.GetDesignSettings()

print('=== 板级设计规则 ===')
print('  min clearance      = %.3f mm' % (ds.m_MinClearance / NM))
print('  copper edge clear  = %.3f mm' % (ds.m_CopperEdgeClearance / NM))
try:
    print('  hole clearance     = %.3f mm' % (ds.m_HoleClearance / NM))
except Exception as e:
    print('  hole clearance     = (读取失败 %s)' % e)
try:
    print('  hole-to-hole       = %.3f mm' % (ds.m_HoleToHoleMin / NM))
except Exception:
    pass
print('  track width        = %.3f mm' % (ds.m_TrackMinWidth / NM))
print()

# ---- 收集所有走线 ----
tracks = []
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    x1, y1, x2, y2 = s.x / NM, s.y / NM, e.x / NM, e.y / NM
    tracks.append({
        'net': t.GetNetname(),
        'layer': 'F.Cu' if t.GetLayer() == pcbnew.F_Cu else 'B.Cu',
        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
        'via': t.GetClass() == 'PCB_VIA',
    })

# ---- Q1：哪些缝隙被占用 ----
# 缝隙 k 位于 J3-k 与 J3-(k+1) 之间，中心 y = J3_Y0 + (k-0.5)*PITCH
print('=== Q1  J3 缝隙占用情况（k = 缝编号，从 J3-1/J3-2 之间开始）===')
gaps = []
for k in range(1, NPIN):
    ymid = J3_Y0 + (k - 0.5) * PITCH
    ylo = J3_Y0 + (k - 1) * PITCH + J3_PAD_HALF
    yhi = J3_Y0 + k * PITCH - J3_PAD_HALF
    occ = []
    for t in tracks:
        if t['via']:
            if abs(t['x1'] - J3_X) < 1.2 and ylo <= t['y1'] <= yhi:
                occ.append((t['net'], t['layer'], 'via@%.2f' % t['y1']))
            continue
        # 该走线是否横穿 x=25.13 且 y 落在缝隙内
        if min(t['x1'], t['x2']) < J3_X < max(t['x1'], t['x2']):
            for yy in (t['y1'], t['y2']):
                if ylo - 0.01 <= yy <= yhi + 0.01:
                    occ.append((t['net'], t['layer'], 'y=%.2f' % yy))
                    break
    gaps.append((k, ymid, ylo, yhi, occ))

for k, ymid, ylo, yhi, occ in gaps:
    tag = '空闲' if not occ else '占用'
    detail = ''
    if occ:
        detail = '  <- ' + ', '.join('%s/%s(%s)' % o for o in occ[:3])
    print('  缝#%-2d y=%.2f (%.2f..%.2f)  %s%s' % (k, ymid, ylo, yhi, tag, detail))

free = [g for g in gaps if not g[4]]
print()
print('  空闲缝隙:', [('缝#%d y=%.2f' % (g[0], g[1])) for g in free])
print()

# ---- Q2：窄沟占用 ----
print('=== Q2  窄沟 x∈[%.2f, %.2f] 占用情况 ===' % (J3_X + J3_PAD_HALF, EAST_EDGE))
T0, T1 = J3_X + J3_PAD_HALF, EAST_EDGE
for t in tracks:
    if t['via']:
        if T0 <= t['x1'] <= T1:
            print('    过孔 %s/%s @ (%.2f,%.2f)' % (t['net'], t['layer'], t['x1'], t['y1']))
        continue
    if min(t['x1'], t['x2']) >= T0 and max(t['x1'], t['x2']) <= T1:
        print('    走线 %s/%s (%.2f,%.2f)->(%.2f,%.2f)'
              % (t['net'], t['layer'], t['x1'], t['y1'], t['x2'], t['y2']))
print()

# ---- Q3：安装孔对窄沟的侵占 ----
print('=== Q3  安装孔（孔径 vs 窄沟）===')
for fp in b.GetFootprints():
    if fp.GetReference().startswith('H'):
        for p in fp.Pads():
            cx, cy = p.GetPosition().x / NM, p.GetPosition().y / NM
            dr = p.GetDrillSize().x / NM
            sz = p.GetSize().x / NM
            attr = p.GetAttribute()
            print('  %s @ (%.2f,%.2f)  drill=%.2f  pad=%.2f  attr=%s'
                  % (fp.GetReference(), cx, cy, dr, sz, attr))
            # 该孔在 x 方向的侵占
            if attr == 3 or dr > 0:
                half = dr / 2
                print('      → 铜需避开孔壁 ±%.3fmm；窄沟东缘=%.2f'
                      % (half, cx - half))
print()

# ---- 关键：在 y 方向上扫一遍，看 x∈[25.93,26.60] 的通道在哪些 y 段可用 ----
print('=== 窄沟可用 y 区间扫描（x∈[%.2f,%.2f]，需避开所有 J3/East 焊盘与孔）===')
import math


def rect_hit(y, x0, x1, y0, y1):
    return not (y < y0 or y > y1)


blocked = []
# J3 列焊盘
for i in range(NPIN):
    cy = J3_Y0 + i * PITCH
    blocked.append((cy - J3_PAD_HALF, cy + J3_PAD_HALF, 'J3-%d' % (i + 1)))
# J4 / J5 / J2 左缘焊盘
for fp in b.GetFootprints():
    if fp.GetReference() not in ('J4', 'J5', 'J2'):
        continue
    for p in fp.Pads():
        cx, cy = p.GetPosition().x / NM, p.GetPosition().y / NM
        half = p.GetSize().x / NM / 2
        if cx - half < EAST_EDGE + 0.01:
            blocked.append((cy - p.GetSize().y / NM / 2,
                            cy + p.GetSize().y / NM / 2,
                            '%s-%s' % (fp.GetReference(), p.GetNumber())))
# 安装孔
for fp in b.GetFootprints():
    if fp.GetReference().startswith('H'):
        for p in fp.Pads():
            cx, cy = p.GetPosition().x / NM, p.GetPosition().y / NM
            r = p.GetDrillSize().x / NM / 2
            blocked.append((cy - r, cy + r, '%s孔' % fp.GetReference()))

blocked.sort()
merged = []
for y0, y1, who in blocked:
    if merged and y0 <= merged[-1][1]:
        merged[-1][1] = max(merged[-1][1], y1)
        merged[-1][2] += '+' + who
    else:
        merged.append([y0, y1, who])
for y0, y1, who in merged:
    print('  y %.2f .. %.2f  被占：%s' % (y0, y1, who))
