# check_offboard.py — 0 个板外焊盘 + 板框闭合/圆角/mid 校验
import math
import pcbnew

BOARD = r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb'
board = pcbnew.LoadBoard(BOARD)

W, H, RC = 44.0, 54.5, 3.0
NM = 1_000_000

# ---- 1. 焊盘板内检查 ----
bad = []
total = 0
for fp in board.GetFootprints():
    for p in fp.Pads():
        total += 1
        x, y = p.GetPosition().x / NM, p.GetPosition().y / NM
        if not (0 <= x <= W and 0 <= y <= H):
            bad.append((fp.GetReference(), p.GetNumber(), round(x, 2), round(y, 2)))
print(f'pads total={total} offboard={len(bad)}')
for b in bad:
    print('  OFFBOARD:', b)

# ---- 2. 板框弧 mid 校验 ----
arcs, segs = [], []
for d in board.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts:
        continue
    sh = d.GetShape()
    if sh == pcbnew.SHAPE_T_ARC:
        c = d.GetCenter()
        s = d.GetStart()
        e = d.GetEnd()
        m = d.GetMid() if hasattr(d, 'GetMid') else None
        r = math.hypot(s.x - c.x, s.y - c.y) / NM
        entry = {'center': (c.x / NM, c.y / NM), 'r': r,
                 'start': (s.x / NM, s.y / NM), 'end': (e.x / NM, e.y / NM),
                 'mid': (m.x / NM, m.y / NM) if m else None}
        if entry['mid']:
            dm = math.hypot(entry['mid'][0] - entry['center'][0],
                            entry['mid'][1] - entry['center'][1])
            entry['mid_r'] = dm
            # mid 必须在板内
            entry['mid_in_board'] = (0 <= entry['mid'][0] <= W and 0 <= entry['mid'][1] <= H)
        arcs.append(entry)
    elif sh == pcbnew.SHAPE_T_SEGMENT:
        segs.append(((d.GetStart().x / NM, d.GetStart().y / NM),
                     (d.GetEnd().x / NM, d.GetEnd().y / NM)))

print(f'edge arcs={len(arcs)} segs={len(segs)}')
ok = True
for i, a in enumerate(arcs):
    print(f"  arc{i}: center={tuple(round(v,2) for v in a['center'])} r={a['r']:.3f} "
          f"mid={tuple(round(v,3) for v in a['mid']) if a['mid'] else None} "
          f"mid_r={a.get('mid_r', float('nan')):.3f} in_board={a.get('mid_in_board')}")
    if a['mid'] and abs(a['mid_r'] - a['r']) > 0.01:
        print('    !! mid radius mismatch'); ok = False
    if a['mid'] and not a['mid_in_board']:
        print('    !! mid outside board'); ok = False

# ---- 3. 轮廓闭合检查（段/弧端点两两相连） ----
pts = []
for s in segs:
    pts.append(('seg', s[0], s[1]))
for a in arcs:
    pts.append(('arc', a['start'], a['end']))
# 每个端点应恰好出现两次
from collections import Counter
cnt = Counter()
for _, p1, p2 in pts:
    cnt[(round(p1[0], 3), round(p1[1], 3))] += 1
    cnt[(round(p2[0], 3), round(p2[1], 3))] += 1
odd = {k: v for k, v in cnt.items() if v != 2}
print('outline endpoints with degree != 2:', len(odd))
for k, v in odd.items():
    print('   ', k, v)
    ok = False

# ---- 4. 中心线尺寸 ----
xs = [p[0] for _, p1, p2 in pts for p in (p1, p2)]
ys = [p[1] for _, p1, p2 in pts for p in (p1, p2)]
print(f'outline centerline bbox: {max(xs)-min(xs):.3f} x {max(ys)-min(ys):.3f} mm (expect {W} x {H})')
print('RESULT:', 'PASS' if (ok and not bad and not odd) else 'FAIL')
