# -*- coding: utf-8 -*-
"""test_rulearea_dsn.py — 验证 KiCad 规则区(rule area)导出到 DSN 的 keepout 语法与位置，
确认 Freerouting 能否识别。"""
import pcbnew
from pcbnew import VECTOR2I, ZONE, SHAPE_POLY_SET

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000
W, H = 44.0, 54.5

b = pcbnew.LoadBoard(BASE + '/hub75-adapter.kicad_pcb')

# 移除铜皮铺铜（保留规则区）
for z in list(b.Zones()):
    if z.GetIsRuleArea():
        continue
    b.Remove(z)

# ---- 建一个 B.Cu 规则区：禁止走线/过孔，允许铺铜 ----
z = ZONE(b)
z.SetIsRuleArea(True)
z.SetDoNotAllowTracks(True)
z.SetDoNotAllowVias(True)
z.SetDoNotAllowPads(False)
z.SetDoNotAllowFootprints(False)
z.SetDoNotAllowZoneFills(False)
z.SetLayer(pcbnew.B_Cu)
ps = SHAPE_POLY_SET()
ps.NewOutline()
for (x, y) in [(0.0, 0.0), (W, 0.0), (W, H), (0.0, H)]:
    ps.Append(int(x * NM), int(y * NM))
z.SetOutline(ps)
b.Add(z)
print('rule area added, isRuleArea =', z.GetIsRuleArea())

out = BASE + '/_test_rulearea.dsn'
pcbnew.ExportSpecctraDSN(b, out)
print('DSN exported ->', out)

s = open(out, encoding='utf-8').read()
lines = s.split('\n')
print('\n--- DSN 中所有 keepout 行及其上下文 ---')
for i, ln in enumerate(lines):
    if 'keepout' in ln:
        lo = max(0, i - 6)
        print('\n>>> line %d context:' % i)
        for j in range(lo, min(len(lines), i + 4)):
            print('   %s%s' % ('>>' if j == i else '  ', lines[j]))
