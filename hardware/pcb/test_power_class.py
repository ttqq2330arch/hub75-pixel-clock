# -*- coding: utf-8 -*-
"""
test_power_class.py — 实测 Freerouting 是否把 DSN 里 (type power) 的网络当作平面处理

原理：
  Specctra DSN 的 class 可以带 (type power) / (type signal) / (type mixed)。
  Freerouting 读入后会给 power 类网络分配「平面连接」策略：
  同网络的多焊盘通过过孔连到该层的铜皮，而不是逐点串线。
  若本板 GND 被标为 power + B.Cu 有 GND 铺铜，则：
    · 6 个 GND 焊盘各打一个过孔连到 B.Cu 平面
    · GND 不再占用 F.Cu 的走线通道 → 给 HUB75 信号让出空间
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
b = pcbnew.LoadBoard(BASE + '/hub75-adapter.kicad_pcb')

ds = b.GetDesignSettings()
ds.m_MinClearance = pcbnew.FromMM(0.2)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
ds.SetCustomTrackWidth(pcbnew.FromMM(0.3))
ds.SetCustomViaDrill(pcbnew.FromMM(0.6))
ds.SetCustomViaSize(pcbnew.FromMM(0.8))
ds.UseCustomTrackViaSize(True)

# 临时移除铺铜（含天线规则区 —— 规则区要保留，让 Freerouting 避让天线）
zones = list(b.Zones())
for z in zones:
    b.Remove(z)
print('zones removed:', len(zones))

pcbnew.ExportSpecctraDSN(b, BASE + '/_test_power.dsn')
print('DSN exported')

DSN = BASE + '/_test_power.dsn'
s = open(DSN, encoding='utf-8').read()

# 把 GND 拆出来单独作为 power class
old_cls = '(class kicad_default'
i = s.find(old_cls)
assert i > 0, 'class not found'
j = s.find(')', s.find('(rule', i))
# 找到 class 块的结束括号（嵌套计数）
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
print('--- 原 class 块 ---')
print(cls_block)

new_cls = '(class kicad_default'
# 从原 class 里去掉 GND
body = cls_block[len(old_cls):]
body = body.replace(' GND ', ' ').replace('(GND ', '(').replace('GND)', ')')
new_cls = old_cls + body

power_cls = ('\n    (class power_gnd GND\n'
             '      (type power)\n'
             '      (circuit\n'
             '        (use_via "Via[0-1]_600:300_um")\n'
             '      )\n'
             '      (rule\n'
             '        (width 200)\n'
             '        (clearance 200)\n'
             '      )\n'
             '    )')

s2 = s[:i] + new_cls + power_cls + s[k + 1:]
open(DSN, 'w', encoding='utf-8').write(s2)
print('--- 新增 power class ---')
print(power_cls)
print('GND 已从 kicad_default 移出，并标记为 (type power)')
