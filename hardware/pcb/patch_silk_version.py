# -*- coding: utf-8 -*-
"""
patch_silk_version.py — 同步丝印版本号到已布线板

★ 为什么单独打补丁而不重跑 gen_board.py → step3_ses.py
  重跑会把已验证的 v2.3 走线全部丢掉（Freerouting v2.4 重跑会丢 4 个网络），
  只改一个字没必要重跑整条流程。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0
OLD = 'HUB75 ADAPTER v2.2'
NEW = 'HUB75 ADAPTER v2.4'

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
n = 0
for d in b.GetDrawings():
    if (d.GetLayer() == pcbnew.F_SilkS and d.GetClass() == 'PCB_TEXT'
            and d.GetText() == OLD):
        d.SetText(NEW)
        n += 1
print('silk text patched:', n)

if n:
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    io.SaveBoard(BASE + '/hub75-adapter-routed.kicad_pcb', b)
    print('saved')
