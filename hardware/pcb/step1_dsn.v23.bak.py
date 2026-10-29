# -*- coding: utf-8 -*-
"""
step1_dsn.py — 导出 Specctra DSN

★ v2.3 最终方案（基于实测数据推翻 v2.2）：
  ── v2.2 的「B.Cu 整板 keepout」是死路，原因是几何而非配置：
     J3 那 21 个通孔焊盘（x=25.13）贯穿全高 1.88→52.68mm，把板子竖着劈开；
     J1(x=2.27) → J2(x=27.9) 的 15 条 HUB75 线必须横穿 J3，
     焊盘间缝仅 2.54−1.6 = 0.94mm，过缝后还要在 J3↔J2 之间 1.17mm 窄通道扇出
     ⇒ 实测 7 个网络（A/E/G1/G2/SCL/SDA/UTX）直接布不通。
     ⇒ B.Cu 必须保留给信号过桥。

  ── v2.2 注入的 (rect pcb B.Cu ...) 也有两个错误，Freerouting 直接忽略了它：
     ① rect 只吃 4 个坐标，v2.2 塞了 8 个
     ② 它被注入在 (structure ...) 块**外面**的 (wiring) 之前
     ⇒ 所以「之前那版布线板」其实是双层方案，GND 被走线切碎就是这么来的。

  ── v2.3 的三个关键改动：
     ① 天线净空改用 KiCad 原生「规则区」(rule area)，
        gen_board.py 里已设 F.Cu+B.Cu 双层 + 禁走线/禁过孔/禁铺铜；
        KiCad 导出 DSN 时自动变成 (keepout "" (polygon F.Cu ...)) / (polygon B.Cu ...)
        ⇒ 不再需要手工注入 keepout，Freerouting 自动避让天线区。
     ② GND 网络从 kicad_default 类里拆出，单独标为 (class power_gnd GND (type power))
        ⇒ Freerouting 把 GND 当电源网络处理，不占用信号走线通道。
        实测：未布通网络从 7 个降到 1 个。
     ③ B.Cu 的 GND 铺铜在 gen_board.py 里已改为 ZONE_CONNECTION_FULL（实心连接），
        6 个 GND 焊盘全是 PTH 通孔 → 焊盘自带 B.Cu 环，与实心铺铜直接融合，
        不依赖花焊盘引线（v2.2 的 J3-1 花焊盘断裂就是这么来的）。
        ⇒ GND **不需要任何走线**，Freerouting 报它 "unrouted" 是可以接受的，
          KiCad 侧由铺铜接管（v2.3 实测 DRC unconnected 里没有 GND）。
     ④ 3V3 手工预布线：Freerouting 两次都在 3V3 上放弃（J1→J4 要横穿 J3 排针列，
        而 F.Cu 上部被 UTX/URX 挤占）。手工规划的 F.Cu 路径见 plan_3v3_f.py，
        自检全过（45° / 间距 / 天线区），以 (wiring ...) 形式注入 DSN，
        Freerouting 会把它当作已完成的走线并绕开。

设计规则：0.2mm 线距 / 0.3mm 板边距 / 0.3mm 线宽 / 0.6mm 过孔钻 / 0.8mm 过孔
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
DSN = BASE + '/hub75-adapter.dsn'

b = pcbnew.LoadBoard(BASE + '/hub75-adapter.kicad_pcb')
ds = b.GetDesignSettings()
ds.m_MinClearance = pcbnew.FromMM(0.2)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
ds.SetCustomTrackWidth(pcbnew.FromMM(0.3))
ds.SetCustomViaDrill(pcbnew.FromMM(0.6))
ds.SetCustomViaSize(pcbnew.FromMM(0.8))
ds.UseCustomTrackViaSize(True)

# ---- 只移除 GND 铺铜，保留天线规则区（规则区要进 DSN 才能让 Freerouting 避让）----
removed = 0
for z in list(b.Zones()):
    if not z.GetIsRuleArea():
        b.Remove(z)
        removed += 1
print('copper zones removed for export:', removed)

pcbnew.ExportSpecctraDSN(b, DSN)
print('DSN exported:', DSN)

# ---- 把 GND 从 kicad_default 拆出，单独标为 (type power) ----
s = open(DSN, encoding='utf-8').read()

i = s.find('(class kicad_default')
assert i > 0, 'class kicad_default not found in DSN'
depth = 0
k = i
while True:
    if s[k] == '(':
        depth += 1
    elif s[k] == ')':
        depth -= 1
        if depth == 0:
            break
    k += 1
cls_block = s[i:k + 1]

# 从类成员列表里剔除 GND
body = cls_block[len('(class kicad_default'):]
body = body.replace(' GND ', ' ').replace('(GND ', '(').replace('GND)', ')')
new_cls = '(class kicad_default' + body

power_cls = (
    '\n    (class power_gnd GND\n'
    '      (type power)\n'
    '      (circuit\n'
    '        (use_via "Via[0-1]_600:300_um")\n'
    '      )\n'
    '      (rule\n'
    '        (width 200)\n'
    '        (clearance 200)\n'
    '      )\n'
    '    )')

s = s[:i] + new_cls + power_cls + s[k + 1:]

# ---- 校验：天线 keepout 必须以 KiCad 原生语法出现在 (structure) 块内 ----
ko_cnt = s.count('(keepout "" (polygon')
struct_end = s.find('\n  (placement')
print('keepout(polygon) in DSN:', ko_cnt, '| structure block ends at', struct_end)
for m in __import__('re').finditer(r'\(keepout "" \(polygon ([A-Za-z.]+)', s):
    print('   keepout layer =', m.group(1))

open(DSN, 'w', encoding='utf-8').write(s)
print('GND -> (class power_gnd (type power)) injected')

# ---- 注入 3V3 的手工预布线（让 Freerouting 把它当已完成走线）----
# 路径来自 plan_3v3_f.py（已逐段自检：45° / 0.2mm 间距 / 不进天线区）
PRE_3V3 = [
    (2.27, 1.88),     # J1-1  起点
    (2.27, 3.15),     # 竖直上行到 y=3.15 车道
    (24.00, 3.15),    # 水平走到 J3 列左侧
    (26.10, 3.15),    # 水平穿过 J3 缝隙#0（y 2.68..3.62）
    (26.95, 4.00),    # 45° 斜下
    (27.40, 4.45),    # 45° 斜下
    (27.40, 5.60),    # 竖直下行到 J4-1
]
D = 10_000
pts = '\n            '.join('%d %d' % (int(round(x * D)), int(round(-y * D)))
                           for (x, y) in PRE_3V3)
wiring = (
    '  (wiring\n'
    '    (net 3V3\n'
    '      (wire\n'
    '        (path F.Cu 3000\n'
    '            %s\n'
    '        )\n'
    '      )\n'
    '    )\n'
    '  )' % pts)

s = open(DSN, encoding='utf-8').read()
assert '  (wiring\n  )' in s, 'empty wiring block not found'
s = s.replace('  (wiring\n  )', wiring, 1)
open(DSN, 'w', encoding='utf-8').write(s)
print('3V3 pre-route injected (%d points, F.Cu, 0.3mm)' % len(PRE_3V3))
