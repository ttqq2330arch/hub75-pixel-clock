import pcbnew
b = pcbnew.LoadBoard(r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb')
ds = b.GetDesignSettings()
print('ds type:', type(ds))
attrs = [a for a in dir(ds) if 'rack' in a or 'learance' in a or 'ia' in a or 'rill' in a]
print('ds attrs:', attrs[:30])
try:
    print('min track width:', ds.GetTrackWidthIndex() if hasattr(ds, 'GetTrackWidthIndex') else '?')
except Exception as e:
    print('e1', e)
print('has m_MinTrackWidth:', hasattr(ds, 'm_MinTrackWidth'))
print('has m_MinClearance:', hasattr(ds, 'm_MinClearance'))
print('has m_MinViaDiameter:', hasattr(ds, 'm_MinViaDiameter'))
print('has m_MinViaDrill:', hasattr(ds, 'm_MinViaDrill'))
print('has m_MinHoleToHole:', hasattr(ds, 'm_MinHoleToHole'))
print('has m_MinThroughHole:', hasattr(ds, 'm_MinThroughHole'))
try:
    print('track width list:', ds.GetTrackWidthList()[:5] if hasattr(ds, 'GetTrackWidthList') else '?')
except Exception as e:
    print('e2', e)
print('has GetNetSettings:', hasattr(b, 'GetNetSettings'))
if hasattr(b, 'GetNetSettings'):
    ns = b.GetNetSettings()
    print('ns type:', type(ns), [a for a in dir(ns) if not a.startswith('_')][:20])
