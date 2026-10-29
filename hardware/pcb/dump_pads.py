import pcbnew
b = pcbnew.LoadBoard(r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb')
for fp in b.GetFootprints():
    ref = fp.GetReference()
    rows = []
    for p in fp.Pads():
        rows.append((p.GetNumber(), p.GetNetname()))
    print(ref, ':', ' '.join(f"{n}:{net}" for n, net in rows))
