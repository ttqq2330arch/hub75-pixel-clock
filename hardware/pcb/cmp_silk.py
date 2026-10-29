# -*- coding: utf-8 -*-
"""
cmp_silk.py — 比对「v2.3 备份布线板」与「当前 gen_board.py 生成的 v2.4 空板」的丝印/装配内容

★ 为什么要比对
  v2.3 布线板是由**更早版本**的 gen_board.py 生成的（时间戳：布线板 18:11 < gen_board 18:24），
  所以必须确认二者的丝印/F.Fab 完全一致，否则「升级到 v2.4」只升了一半。
"""
import pcbnew

BASE = r'F:/AI数据/hub75-pixel-clock/hardware/pcb'
NM = 1_000_000.0


def collect(path):
    b = pcbnew.LoadBoard(path)
    silk = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS and d.GetClass() == 'PCB_TEXT':
            silk.append((d.GetText(),
                         round(d.GetPosition().x / NM, 2),
                         round(d.GetPosition().y / NM, 2)))
    silk.sort()

    fab = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.F_Fab and d.GetClass() == 'PCB_TEXT':
            fab.append((d.GetText(),
                        round(d.GetPosition().x / NM, 2),
                        round(d.GetPosition().y / NM, 2)))
    fab.sort()

    # 封装 + 焊盘位置
    fps = []
    for fp in b.GetFootprints():
        pads = []
        for p in fp.Pads():
            pos = p.GetPosition()
            pads.append((p.GetNumber(), p.GetNetname(),
                         round(pos.x / NM, 3), round(pos.y / NM, 3),
                         round(p.GetSize().x / NM, 2), round(p.GetSize().y / NM, 2),
                         p.GetShape(), p.GetAttribute()))
        pads.sort(key=lambda t: int(t[0]) if t[0].isdigit() else 0)
        fps.append((fp.GetReference(), fp.GetValue(),
                    round(fp.GetPosition().x / NM, 2),
                    round(fp.GetPosition().y / NM, 2), pads))
    fps.sort()

    # 焊盘网络
    nets = sorted({p.GetNetname() for fp in b.GetFootprints()
                   for p in fp.Pads() if p.GetNetname()})
    return silk, fab, fps, nets


s1, f1, p1, n1 = collect(BASE + '/hub75-adapter-routed.v23.bak.kicad_pcb')
s2, f2, p2, n2 = collect(BASE + '/hub75-adapter.kicad_pcb')

print('=' * 78)
print('=== 丝印 F.SilkS 文字 ===')
print('  v2.3 布线板: %d 条   v2.4 空板: %d 条' % (len(s1), len(s2)))
if s1 == s2:
    print('  >>> 完全一致 ✓')
else:
    only1 = [x for x in s1 if x not in s2]
    only2 = [x for x in s2 if x not in s1]
    for x in only1:
        print('  仅 v2.3 有:', x)
    for x in only2:
        print('  仅 v2.4 有:', x)

print()
print('=== F.Fab 装配文字 ===')
print('  v2.3: %d 条   v2.4: %d 条' % (len(f1), len(f2)))
if f1 == f2:
    print('  >>> 完全一致 ✓')
else:
    for x in [x for x in f1 if x not in f2]:
        print('  仅 v2.3 有:', x)
    for x in [x for x in f2 if x not in f1]:
        print('  仅 v2.4 有:', x)

print()
print('=== 封装与焊盘 ===')
if p1 == p2:
    print('  >>> 完全一致 ✓（%d 个封装）' % len(p1))
else:
    print('  封装数 v3=%d v4=%d' % (len(p1), len(p2)))
    for a, b in zip(p1, p2):
        if a != b:
            print('  差异封装:', a[0], '/', b[0])
            if a[:4] != b[:4]:
                print('    位置/值不同:', a[:4], 'vs', b[:4])
            for pa, pb in zip(a[4], b[4]):
                if pa != pb:
                    print('    焊盘差异:', pa, 'vs', pb)

print()
print('=== 网络集合 ===')
print('  v2.3:', n1)
print('  v2.4:', n2)
print('  >>>', '一致 ✓' if n1 == n2 else '不一致 ✗')
