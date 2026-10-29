# -*- coding: utf-8 -*-
"""
analyze_ses.py — 解析 Freerouting 输出的 SES，找出「哪些焊盘没有被布线覆盖」。

SES 结构:  (network_out (net NAME (wire (path LAYER W x1 y1 x2 y2 ...)))) )
坐标单位: 0.1µm（10000 = 1mm）

用法: "F:/Tools/KiCad/bin/python.exe" analyze_ses.py <board.kicad_pcb> <out.ses>
"""
import re
import sys
import pcbnew

NM = 1_000_000
SES_UNIT = 10000.0     # SES 坐标 → mm
PCB = sys.argv[1]
SES = sys.argv[2]

b = pcbnew.LoadBoard(PCB)

pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if not n:
            continue
        pads.append((n, '%s-%s' % (fp.GetReference(), p.GetNumber()),
                     p.GetPosition().x / NM, p.GetPosition().y / NM))

txt = open(SES, encoding='utf-8', errors='replace').read()

# 抓取所有 (net NAME ... ) 块 —— 用括号配平，避免贪婪匹配吞掉后续块
nets = {}


def extract_blocks(t, opener):
    """返回 opener 之后所有同层括号块的 (name, body)"""
    out = []
    i = 0
    while True:
        i = t.find(opener, i)
        if i < 0:
            break
        # opener 形如 "(net "
        name_end = t.find(' ', i + len(opener))
        name = t[i + len(opener):name_end].strip().strip('"')
        # 从 name_end 处的 '(' 开始配平
        depth = 0
        j = name_end
        while j < len(t):
            if t[j] == '(':
                depth += 1
            elif t[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((name, t[name_end:j]))
        i = j
    return out


for name, blk in extract_blocks(txt, '(net '):
    paths = []
    # (path LAYER W  x1 y1 x2 y2 ...)  —— 顶点可能跨多行
    for pm in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+((?:-?[\d.]+\s+-?[\d.]+\s*)+)\)', blk):
        lay = pm.group(1)
        nums = [float(v) for v in pm.group(3).split()]
        pts = list(zip(nums[0::2], nums[1::2]))
        for i in range(len(pts) - 1):
            # ★ Freerouting 的 Y 轴向上，KiCad 向下 → y 取反
            paths.append((lay, pts[i][0] / SES_UNIT, -pts[i][1] / SES_UNIT,
                          pts[i + 1][0] / SES_UNIT, -pts[i + 1][1] / SES_UNIT))
    vias = []
    for vm in re.finditer(r'\(via\s+(\S*)\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\S+)\s*\)', blk):
        vias.append((float(vm.group(2)) / SES_UNIT, -float(vm.group(3)) / SES_UNIT))
    if paths or vias:
        nets[name] = {'paths': paths, 'vias': vias}

TOL = 0.06   # mm


def seg_dist(px, py, x1, y1, x2, y2):
    """点到线段的最短距离"""
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = ((px - x1) * dx + (py - y1) * dy) / L2
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


print('board:', PCB)
print('ses  :', SES)
print('')
print('=== SES 各网络布线量 ===')
for n in sorted(nets):
    lay_cnt = {}
    for (lay, x1, y1, x2, y2) in nets[n]['paths']:
        lay_cnt[lay] = lay_cnt.get(lay, 0) + 1
    print('  %-6s 线段 %3d  过孔 %2d  层 %s'
          % (n, len(nets[n]['paths']), len(nets[n]['vias']), lay_cnt))

print('')
print('=== 未被走线覆盖的焊盘（点到线段距离 > 0.85mm 即视为未接入）===')
miss = []
for (n, ref, px, py) in pads:
    hit = False
    for (lay, x1, y1, x2, y2) in nets.get(n, {}).get('paths', []):
        if seg_dist(px, py, x1, y1, x2, y2) <= 0.85:
            hit = True
            break
    if not hit:
        miss.append((n, ref, px, py))
if miss:
    for (n, ref, px, py) in miss:
        print('  [X] %-6s %-8s @ (%.2f, %.2f)' % (n, ref, px, py))
    print('  ⇒ %d 个焊盘未覆盖' % len(miss))
else:
    print('  OK —— 每个焊盘都有走线接入 ✓')

print('')
print('网络数: SES %d / 板上有网络焊盘 %d'
      % (len(nets), len(set(p[0] for p in pads))))
