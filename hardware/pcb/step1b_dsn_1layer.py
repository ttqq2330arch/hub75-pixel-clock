# step1b_dsn_1layer.py — 生成单层（仅 F.Cu）DSN，强制所有信号走顶层，底层留给 GND 铺铜
import re

SRC = r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.dsn'
DST = r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter-1l.dsn'

text = open(SRC, 'r', encoding='utf-8').read()
# 删除 B.Cu 层定义块
pat = re.compile(r'\s*\(layer B\.Cu\s*\(type signal\)\s*\(property\s*\(index 1\)\s*\)\s*\)', re.S)
new, n = pat.subn('', text)
print('B.Cu layer blocks removed:', n)
assert n == 1
open(DST, 'w', encoding='utf-8').write(new)
print('written:', DST)
