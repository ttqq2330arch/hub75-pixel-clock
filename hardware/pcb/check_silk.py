# -*- coding: utf-8 -*-
"""
check_silk.py — 丝印自动体检（比人眼看渲染图可靠）

检查 4 类问题：
  1) 丝印文字越出板框（打样会被铣边切掉）
  2) 丝印文字互相重叠（压字）
  3) 丝印文字压到焊盘 / 走线（阻焊层露铜，打样外观差、也可能被判 DRC 违规）
  4) 丝印文字压到安装孔

用法: "F:/Tools/KiCad/bin/python.exe" check_silk.py
"""
import math
import pcbnew

PCB = r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb'
NM = 1_000_000

board = pcbnew.LoadBoard(PCB)


def bbox(t):
    """返回 (x0,y0,x1,y1) mm，KiCad 的 bbox 含字形实际外框"""
    b = t.GetBoundingBox()
    return (b.GetLeft() / NM, b.GetTop() / NM,
            b.GetRight() / NM, b.GetBottom() / NM)


def overlap(a, b, gap=0.0):
    """两矩形是否重叠（gap 为要求的最小间距 mm）"""
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or
                a[3] + gap <= b[1] or b[3] + gap <= a[1])


# ---------- 收集丝印文字 ----------
texts = []
for dr in board.GetDrawings():
    if dr.GetLayer() == pcbnew.F_SilkS and dr.GetClass() == 'PCB_TEXT':
        t = dr
        bb = bbox(t)
        texts.append({
            'txt': t.GetText(),
            'bb': bb,
            'x': t.GetPosition().x / NM,
            'y': t.GetPosition().y / NM,
        })

# ---------- 收集焊盘（含铜箔外形）----------
pads = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        pos = p.GetPosition()
        bb = p.GetBoundingBox()
        pads.append({
            'ref': fp.GetReference(),
            'num': p.GetNumber(),
            'bb': (bb.GetLeft() / NM, bb.GetTop() / NM,
                   bb.GetRight() / NM, bb.GetBottom() / NM),
            'x': pos.x / NM, 'y': pos.y / NM,
            'npth': p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
        })

# ---------- 板框中心线矩形（含圆角，按外接矩形保守算）----------
edge = []
for dr in board.GetDrawings():
    if dr.GetLayer() == pcbnew.Edge_Cuts:
        s = dr.GetStart()
        e = dr.GetEnd()
        edge.append((min(s.x, e.x) / NM, min(s.y, e.y) / NM,
                     max(s.x, e.x) / NM, max(s.y, e.y) / NM))
BX0 = min(e[0] for e in edge)
BY0 = min(e[1] for e in edge)
BX1 = max(e[2] for e in edge)
BY1 = max(e[3] for e in edge)

err = []
warn = []

# ---------- 1) 越板边 ----------
EDGE_KEEP = 0.30   # 距板边至少 0.3mm
for t in texts:
    x0, y0, x1, y1 = t['bb']
    if (x0 < BX0 + EDGE_KEEP or y0 < BY0 + EDGE_KEEP or
            x1 > BX1 - EDGE_KEEP or y1 > BY1 - EDGE_KEEP):
        err.append('越板边: "%s" bbox=(%.2f,%.2f)-(%.2f,%.2f) 板框=(%.2f,%.2f)-(%.2f,%.2f)'
                   % (t['txt'], x0, y0, x1, y1, BX0, BY0, BX1, BY1))

# ---------- 2) 文字互压 ----------
for i in range(len(texts)):
    for j in range(i + 1, len(texts)):
        a, b = texts[i], texts[j]
        if overlap(a['bb'], b['bb']):
            err.append('文字互压: "%s" @y=%.2f  ×  "%s" @y=%.2f'
                       % (a['txt'], a['y'], b['txt'], b['y']))

# ---------- 3) 压焊盘 ----------
for t in texts:
    for p in pads:
        if p['npth']:
            continue
        if overlap(t['bb'], p['bb']):
            err.append('文字压焊盘: "%s" @y=%.2f  ×  %s-%s @(%s,%s)'
                       % (t['txt'], t['y'], p['ref'], p['num'],
                          p['x'], p['y']))

# ---------- 4) 压安装孔 ----------
for t in texts:
    for p in pads:
        if not p['npth']:
            continue
        if overlap(t['bb'], p['bb']):
            err.append('文字压安装孔: "%s" @y=%.2f  ×  %s-%s @(%s,%s)'
                       % (t['txt'], t['y'], p['ref'], p['num'],
                          p['x'], p['y']))

# ---------- 5) 汇总信息 ----------
print('board edge bbox: (%.2f,%.2f)-(%.2f,%.2f)' % (BX0, BY0, BX1, BY1))
print('silk texts: %d   pads: %d' % (len(texts), len(pads)))
print('')

print('--- 丝印文字清单（含 bbox 与到板边余量）---')
for t in sorted(texts, key=lambda z: (z['y'], z['x'])):
    x0, y0, x1, y1 = t['bb']
    margin = min(x0 - BX0, y0 - BY0, BX1 - x1, BY1 - y1)
    flag = '' if margin >= EDGE_KEEP else '  <== 贴边!'
    print('  y=%6.2f x=%6.2f  w=%5.2f h=%4.2f  margin=%5.2f  "%s"%s'
          % (t['y'], t['x'], x1 - x0, y1 - y0, margin, t['txt'], flag))

print('')
print('=== 问题 %d 条 ===' % len(err))
for e in err:
    print('  [X] ' + e)
for w in warn:
    print('  [!] ' + w)
if not err:
    print('RESULT: PASS — 丝印无越边 / 无互压 / 无压焊盘')
else:
    print('RESULT: FAIL — 需修正 %d 处' % len(err))
