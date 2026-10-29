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
# ★ v2.4 修正：上一版的注入语法和单位**两处都错**，整条线被放大 10 倍扔到板外，
#   Freerouting 直接丢弃（这是 3V3 一直布不通的真正根因，不是几何问题）。
#   权威依据 = 用 KiCad 官方 ExportSpecctraDSN 导出已布线板得到的 _ref_routed.dsn：
#     ① 坐标单位是 **1/1000 mm**（板宽 44000 = 44mm），不是 1/10000
#     ② 语法是**扁平单行**：(wire (path 层 宽 x1 y1 x2 y2)(net 名)(type route))
#     ③ 宽度 200 = 0.2mm，坐标可带一位小数
#   并已做受控实验验证：把含预布线的 DSN 喂给 Freerouting，
#   它把预布线原样保留为 (type protect)，只把原本就缺的那 1 个网络当未布通项。
#
# ★ 路径依据 check_3v3_b.py（真·线段-线段最短距离，最小净距 0.381mm）：
#   F.Cu: (2.270,4.419) →(21.719,4.419) →(22.900,5.600)  45° 斜下
#   过孔 (22.900,5.600)
#   B.Cu: (22.900,5.600) →(27.400,5.600)  水平穿 J3-2/J3-3 之间的缝隙
#   为什么长段放 F.Cu：F.Cu 无铺铜，只有 B.Cu 有 GND 铜皮，
#   长段走 F.Cu 才不会切断铜皮；B.Cu 只用 x[22.9,27.4] 一小段。
PRE_3V3_F = [
    (2.270, 4.419),     # J1-2 起点
    (21.719, 4.419),    # 水平长段
    (22.900, 5.600),    # 45° 斜下
]
PRE_3V3_B = [
    (22.900, 5.600),    # 过孔位置
    (27.400, 5.600),    # J4-1 焊盘中心
]
VIA_3V3 = (22.900, 5.600)

s = open(DSN, encoding='utf-8').read()
assert '  (wiring\n  )' in s, 'empty wiring block not found'


def _wire(layer, pts, net='3V3', width=200):
    """按 KiCad 原生扁平单行语法生成一条预布线。"""
    flat = '  '.join('%g %g' % (round(x * 1000, 1), round(-y * 1000, 1))
                      for (x, y) in pts)
    return '    (wire (path %s %d  %s)(net %s)(type route))\n' % (
        layer, width, flat, net)


def _via(x, y, net='3V3'):
    """按 KiCad 原生语法生成一个过孔。
    权威依据 _ref_routed.dsn：
      (via "Via[0-1]_600:300_um"  22000.3 -29727.4 (net B)(type route))
    """
    return '    (via "Via[0-1]_600:300_um"  %g %g (net %s)(type route))\n' % (
        round(x * 1000, 1), round(-y * 1000, 1), net)


wiring = '  (wiring\n'
wiring += _wire('F.Cu', PRE_3V3_F)
wiring += _via(*VIA_3V3)
wiring += _wire('B.Cu', PRE_3V3_B)
wiring += '  )'

s = s.replace('  (wiring\n  )', wiring, 1)
open(DSN, 'w', encoding='utf-8').write(s)
print('3V3 pre-route injected: F.Cu %d pts + via + B.Cu %d pts (unit=1/1000mm)'
      % (len(PRE_3V3_F), len(PRE_3V3_B)))
for line in wiring.strip().splitlines():
    print('   ', line.strip())
