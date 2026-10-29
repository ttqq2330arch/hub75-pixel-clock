# -*- coding: utf-8 -*-
"""
verify_gerber.py — 独立校验导出的 Gerber 是否忠实反映源板

★ 交付前的最后一道关（不信任"导出成功"就宣布完成）
  ① Edge_Cuts：板框闭合、尺寸 = 44 × 54.5mm
  ② F_Cu / B_Cu：都有实际内容（非空）
  ③ B_Cu 含 GND 铺铜 ⇒ 面积占比应显著大于 F.Cu
  ④ 钻孔文件：PTH 孔数 = 焊盘 PTH 数 + 过孔数；NPTH = 4 个 M2.5
  ⑤ 无 0 长度走线 / 无孤立焊盘
"""
import os
import re

import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
G = BASE + '/gerber'
NM = 1_000_000.0

# ---------------- ① Edge_Cuts 板框 ----------------
ec = open(os.path.join(G, 'hub75-adapter-routed-Edge_Cuts.gbr'), encoding='utf-8').read()
pts = []
for m in re.finditer(r'X(-?\d+)Y(-?\d+)D0[123]\*', ec):
    pts.append((int(m.group(1)) / 1e6, int(m.group(2)) / 1e6))
if not pts:
    for m in re.finditer(r'X(-?\d+)Y(-?\d+)D0[123]', ec):
        pts.append((int(m.group(1)) / 1e6, int(m.group(2)) / 1e6))
xs = [p[0] for p in pts]
ys = [p[1] for p in pts]
print('=== ① Edge_Cuts 板框 ===')
print('  顶点数: %d' % len(pts))
if pts:
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    print('  尺寸: %.3f × %.3f mm  (期望 44.000 × 54.500)' % (w, h))
    ok_edge = abs(w - 44.0) < 0.01 and abs(h - 54.5) < 0.01
    print('  ', 'OK ✓' if ok_edge else '<<< 不符 ✗')
else:
    ok_edge = False
    print('  <<< 未解析到板框 ✗')

# ---------------- ② 铜层内容 ----------------
print()
print('=== ② 铜层 Gerber 内容量 ===')
cu_info = {}
for lay in ('F_Cu', 'B_Cu'):
    s = open(os.path.join(G, 'hub75-adapter-routed-%s.gbr' % lay),
             encoding='utf-8').read()
    n_d01 = len(re.findall(r'D01\*', s))
    n_g36 = len(re.findall(r'G36\*', s))     # 填充区（铺铜）
    n_g37 = len(re.findall(r'G37\*', s))
    cu_info[lay] = (n_d01, n_g36)
    print('  %-6s  直线段 %6d   填充区(G36) %4d   文件 %7d B'
          % (lay, n_d01, n_g36, len(s)))
ok_cu = cu_info['F_Cu'][0] > 0 and cu_info['B_Cu'][0] > 0
print('  ', 'OK ✓ 两层都有内容' if ok_cu else '<<< 有空层 ✗')

# ---------------- ③ 铺铜对比 ----------------
print()
print('=== ③ 铺铜验证：B.Cu 应远大于 F.Cu（F.Cu 无铺铜）===')
fb, bb = cu_info['F_Cu'][1], cu_info['B_Cu'][1]
print('  F.Cu 填充区: %d    B.Cu 填充区: %d' % (fb, bb))
ok_zone = (fb == 0 and bb > 0)
print('  ', 'OK ✓ F.Cu 无铺铜、B.Cu 有铺铜' if ok_zone
      else '<<< 铺铜分布异常 ✗')

# ---------------- ④ 钻孔 ----------------
print()
print('=== ④ 钻孔文件核对 ===')
pth = open(os.path.join(G, 'hub75-adapter-routed-PTH.drl'), encoding='utf-8').read()
npth = open(os.path.join(G, 'hub75-adapter-routed-NPTH.drl'), encoding='utf-8').read()

pth_hits = re.findall(r'^X(-?[\d.]+)Y(-?[\d.]+)', pth, re.M)
npth_hits = re.findall(r'^X(-?[\d.]+)Y(-?[\d.]+)', npth, re.M)
print('  PTH 孔数: %d   NPTH 孔数: %d' % (len(pth_hits), len(npth_hits)))

b = pcbnew.LoadBoard(BASE + '/hub75-adapter-routed.kicad_pcb')
pads_pth = 0
pads_npth = 0
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            pads_npth += 1
        else:
            pads_pth += 1
vias = sum(1 for t in b.GetTracks() if t.GetClass() == 'PCB_VIA')
print('  源板: PTH焊盘 %d + 过孔 %d = %d   NPTH焊盘 %d'
      % (pads_pth, vias, pads_pth + vias, pads_npth))
ok_drill = (len(pth_hits) == pads_pth + vias and len(npth_hits) == pads_npth == 4)
print('  ', 'OK ✓ 孔数完全对应' if ok_drill else '<<< 孔数不符 ✗')

# 钻孔直径
for name, txt in (('PTH', pth), ('NPTH', npth)):
    tools = re.findall(r'^T(\d+)C([\d.]+)', txt, re.M)
    print('  %s 钻头: %s' % (name, ', '.join(
        'T%s=%.3fmm' % (tn, float(td)) for tn, td in tools)))

# ---------------- ⑤ 源板几何自检 ----------------
print()
print('=== ⑤ 源板几何自检 ===')
zero_len = 0
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        continue
    s, e = t.GetStart(), t.GetEnd()
    if s.x == e.x and s.y == e.y:
        zero_len += 1
print('  零长度走线: %d' % zero_len)

# 焊盘网络完整性
# ★ 允许列表：这些焊盘"无网络"是设计意图，不是漏接
#   - H1~H4：4 个 NPTH 安装孔（机械固定，无电气）
#   - J1-3(RST) J1-13(GPIO3) J1-14(GPIO46) J1-20(GPIO14) J1-21(5V)
#     → DevKit 侧本板不占用（5V 特意不接，避免与 3V3 打架）
#   - J3-4,5,8..20：JTAG/PSRAM/USB/strapping 等未用脚
ALLOWED_NO_NET = set(['H1', 'H2', 'H3', 'H4']) | {
    'J1-%d' % n for n in (3, 13, 14, 20, 21)} | {
    'J3-%d' % n for n in (4, 5) + tuple(range(8, 21))}

pad_no_net = []
pad_no_net_bad = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if not p.GetNetname():
            tag = fp.GetReference() + '-' + p.GetNumber()
            # 安装孔（NPTH）焊盘号为空串
            key = fp.GetReference() if p.GetNumber() == '' else tag
            if key in ALLOWED_NO_NET or tag in ALLOWED_NO_NET:
                pad_no_net.append(tag)
            else:
                pad_no_net_bad.append(tag)
print('  无网络焊盘: %d 个（其中 %d 个为设计意图的悬空/安装孔）'
      % (len(pad_no_net) + len(pad_no_net_bad), len(pad_no_net)))
print('  非预期无网络焊盘: %s'
      % (', '.join(pad_no_net_bad) if pad_no_net_bad else '无 ✓'))

tracks = list(b.GetTracks())
widths = sorted({round(t.GetWidth() / NM, 3) for t in tracks
                  if t.GetClass() != 'PCB_VIA'})
viasizes = sorted({round(t.GetWidth(pcbnew.F_Cu) / NM, 3) for t in tracks
                   if t.GetClass() == 'PCB_VIA'})
print('  走线线宽集合: %s mm' % widths)
print('  过孔直径集合: %s mm' % viasizes)
print('  走线/过孔总数: %d' % len(tracks))

ok_geom = (zero_len == 0 and len(pad_no_net_bad) == 0
           and widths == [0.2] and viasizes == [0.6])

print()
print('=' * 74)
allok = all([ok_edge, ok_cu, ok_zone, ok_drill, ok_geom])
if allok:
    print('>>> Gerber 交付包自检全部通过 ✓')
else:
    print('!! 存在问题 ✗')
print('=' * 74)
