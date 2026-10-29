#!/usr/bin/env python3
# gen_push_page_gz.py — 把 src/faces_web.h 里内嵌的 PUSH_PAGE（网页推送器成品，
# 96KB 含 6 表盘 base64）gzip 后生成 src/push_page_gz.h（PROGMEM 二进制数组），
# 首页走 Content-Encoding: gzip 秒开（96KB -> 13.4KB，弱信号 8s -> 1s 内）。
# 改了 push_page_template.html 后流程：先 gen_faces_web.py 再跑本脚本。
import gzip, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(ROOT, 'src', 'faces_web.h')
out_path = os.path.join(ROOT, 'src', 'push_page_gz.h')

s = open(src_path, 'rb').read()
m = re.search(rb'R"PWGL\((.*?)\)PWGL"', s, re.S)
if not m:
    raise SystemExit('PUSH_PAGE not found in faces_web.h')
html = m.group(1)
gz = gzip.compress(html, compresslevel=9)
print('PUSH_PAGE raw %d -> gz %d (%.0f%%)' % (len(html), len(gz), 100.0 * len(gz) / len(html)))

lines = [
    '// push_page_gz.h - auto-generated, DO NOT EDIT!',
    '// source: src/faces_web.h PUSH_PAGE (gzip -9, %d -> %d bytes)' % (len(html), len(gz)),
    '// regen:  python tools/gen_push_page_gz.py',
    '#pragma once',
    '#include <Arduino.h>',
    '',
    'static const uint8_t PUSH_PAGE_GZ[] PROGMEM = {',
]
row = []
for b in gz:
    row.append('0x%02X,' % b)
    if len(row) == 16:
        lines.append('  ' + ''.join(row))
        row = []
if row:
    lines.append('  ' + ''.join(row))
lines.append('};')
lines.append('')
lines.append('static const size_t PUSH_PAGE_GZ_LEN = %d;' % len(gz))
lines.append('')
open(out_path, 'w').write('\n'.join(lines))
print('written', out_path)
