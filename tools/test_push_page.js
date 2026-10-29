#!/usr/bin/env node
// test_push_page.js — 推送页面 JS 的 DOM-stub 运行时测试
// 用法：node test_push_page.js [html路径]
// 覆盖：语法编译、表盘库渲染、齿轮按钮、叠加层对话框（两种模式）、
//       画布点击定位、微调、/dialov 保存参数。改页面后必须跑过再烧录。
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HTML = process.argv[2] ||
  path.join(__dirname, '..', 'src', 'faces_web.h');

// ---- 取 HTML：faces_web.h 是 PROGMEM raw string，直接剥掉头尾 ----
let html = fs.readFileSync(HTML, 'utf8');
if (html.includes('R"PWGL(')) {
  html = html.split('R"PWGL(')[1].split(')PWGL"')[0];
}
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('FAIL: 找不到 <script>'); process.exit(1); }
let js = m[1]
  .replace('/*__FACES__*/', '[]')
  .replace('/*__DIALS__*/', '[]');

// ---- 1) 语法检查 ----
try { new Function(js); console.log('[1] 语法编译 OK'); }
catch (e) { console.error('FAIL 语法错误:', e.message); process.exit(1); }

// ---- 2) DOM stub ----
const calls = [];
const dials = [
  { n: 'ult-mario', c: 1, f: 1, o: 1, b: 0, s: 8192, m: 1, x: 12, y: 11, x2: 34, sc: 2, fg: 0 },
  { n: 'mario-coin', c: 10, f: 6, o: 1, b: 1, s: 81920, m: 0, x: -1, y: 46, x2: 34, sc: 2, fg: 0 },
  { n: 'cwp-pikachu', c: 32, f: 12, o: 1, b: 0, s: 262144, m: 0, x: 17, y: 10, x2: 34, sc: 1, fg: 1 },
  { n: 'castlevania', c: 1, f: 1, o: 1, b: 0, s: 8192, m: 0, x: -1, y: 46, x2: 34, sc: 2, fg: 0 },
];
const PREVIEW_B64 = Buffer.alloc(8192, 0x1c).toString('base64');  // 假帧数据

function mkCtx() {
  return {
    fillStyle: '', font: '', textAlign: '', textBaseline: '',
    fillRect() {}, fillText() {}, putImageData() {},
    createImageData(w, h) { return { data: new Uint8ClampedArray(w * h * 4), width: w, height: h }; },
  };
}
function mkEl(tag) {
  const el = {
    tagName: tag, children: [], style: {}, value: '', textContent: '', title: '',
    classList: { add() {}, remove() {}, toggle() {} },
    _ctx: null,
    appendChild(c) { this.children.push(c); return c; },
    getContext() { if (!this._ctx) this._ctx = mkCtx(); return this._ctx; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 64, height: 64 }; },
    addEventListener() {},
  };
  return el;
}
const byId = {};
const dgrid = mkEl('div');
['grid', 'dgrid', 'fwrow', 'st', 'toast', 'mask', 'dlg', 'big', 'dname', 'pbtn',
 'prog', 'cbtn', 'ovmask', 'ovdlg', 'ovcv', 'ovtitle', 'ovpos', 'ovm0', 'ovm1',
 'ovsc', 'ovfg', 'ovscw', 'ovfgw', 'ovup', 'ovdown', 'ovleft', 'ovright', 'ovreset', 'ovsave',
 'ovclose', 'animst', 'aprog', 'animload', 'animsave', 'animfile', 'animpush',
 'fps', 'ovl', 'dialsave'].forEach(id => { byId[id] = mkEl('div'); });
byId['dgrid'] = dgrid;
byId['ovsc'] = Object.assign(mkEl('select'), { value: '2' });

const documentStub = {
  getElementById(id) { return byId[id] || (byId[id] = mkEl('div')); },
  createElement(tag) { return mkEl(tag); },
};

function fetchStub(url, opts) {
  calls.push({ url, method: (opts && opts.method) || 'GET' });
  let body;
  if (url.startsWith('/diallist')) body = { dials };
  else if (url.startsWith('/dialpreview')) body = PREVIEW_B64;
  else if (url.startsWith('/animlist')) body = { frames: 10, fps: 6, overlay: 1, burst: 1, cap: 64, fs: 1, ovmode: 0, ovx: -1, ovy: 46, ovx2: 34, ovs: 2 };
  else if (url.startsWith('/status')) body = { ip: '192.168.1.50', rssi: -59, push: 2 };
  else body = 'OK';
  const isJson = typeof body === 'object' && !(body instanceof String);
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
  });
}

const sandbox = {
  document: documentStub,
  fetch: fetchStub,
  atob: (b) => Buffer.from(b, 'base64').toString('binary'),
  setTimeout, clearTimeout, setInterval, clearInterval,
  console,
};
vm.createContext(sandbox);

// ---- 3) 运行页面脚本 ----
let pageExports = null;
try {
  pageExports = vm.runInContext(js + '\n;({openOv:openOv, ov:ov, ovRender:ovRender, ovNudge:ovNudge, loadDialGallery:loadDialGallery, pushFsDial:pushFsDial, dialInfo:dialInfo});', sandbox, { timeout: 5000 });
  console.log('[2] 页面脚本运行 OK');
} catch (e) { console.error('FAIL 运行错误:', e.stack); process.exit(1); }

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  await sleep(120);   // 等 loadDialGallery / poll / animPoll 的 promise 链跑完

  // ---- 4) 表盘库渲染 ----
  const cells = dgrid.children.filter(c => c.tagName === 'div');
  const fail = (msg) => { console.error('FAIL:', msg); process.exit(1); };
  if (cells.length !== dials.length) fail(`表盘单元格数 ${cells.length} != ${dials.length}`);
  const gears = cells.map(c => c.children.find(k => k.className === 'gear'));
  if (gears.some(g => !g || !g.onclick)) fail('有单元格缺齿轮按钮/onclick');
  console.log(`[3] 表盘库渲染 OK（${cells.length} 格 + ${gears.filter(Boolean).length} 齿轮）`);

  // ---- 5) 打开 ult-mario 调整框 ----
  calls.length = 0;
  gears[0].onclick({ stopPropagation() {} });
  await sleep(60);
  if (!calls.some(c => c.url.startsWith('/dialpreview?name=ult-mario'))) fail('未请求 ult-mario 预览');
  if (!byId['ovmask'].classList.add) fail('ovmask stub 异常');
  console.log('[4] 调整框打开 + 预览请求 OK');

  // ---- 6) 方块模式：点画布定位 ----
  pageExports.ov.mode = 1; pageExports.ovRender();      // 直接走内部态
  byId['ovcv'].onclick({ clientX: 20, clientY: 15 });
  if (pageExports.ov.ox !== 20 || pageExports.ov.oy !== 15 || pageExports.ov.ox2 !== 42)
    fail(`方块点击定位错: ox=${pageExports.ov.ox} oy=${pageExports.ov.oy} ox2=${pageExports.ov.ox2}`);
  pageExports.ovNudge(1, 1);
  if (pageExports.ov.ox !== 21 || pageExports.ov.oy !== 16 || pageExports.ov.ox2 !== 43)
    fail(`方块微调错: ox=${pageExports.ov.ox} oy=${pageExports.ov.oy} ox2=${pageExports.ov.ox2}`);
  // 边界钳制
  pageExports.ov.ox = 44; pageExports.ov.ox2 = 44; pageExports.ovNudge(1, 0);
  if (pageExports.ov.ox !== 45 || pageExports.ov.ox2 !== 45) fail('方块右边界未钳制');
  pageExports.ov.oy = 45; pageExports.ovNudge(0, 1);
  if (pageExports.ov.oy !== 45) fail('方块下边界未钳制');
  console.log('[5] 方块模式点击/微调/钳制 OK');

  // ---- 7) 保存 → /dialov 参数 ----
  calls.length = 0;
  pageExports.ov.ox = 21; pageExports.ov.oy = 16; pageExports.ov.ox2 = 43;  // 复位边界测试改过的状态
  byId['ovsave'].onclick();
  await sleep(30);
  const save = calls.find(c => c.url.startsWith('/dialov'));
  if (!save) fail('未发 /dialov');
  const q = new URL('http://x' + save.url).searchParams;
  const want = { name: 'ult-mario', mode: '1', ox: '21', oy: '16', ox2: '43', ovs: '2' };
  for (const k of Object.keys(want))
    if (q.get(k) !== want[k]) fail(`/dialov ${k}=${q.get(k)} 期望 ${want[k]}`);
  console.log('[6] /dialov 保存参数 OK ->', save.url);

  // ---- 8) 经典模式 + 前景色 ----
  pageExports.ov.mode = 0; pageExports.ov.ox = -1; pageExports.ov.oy = 46; pageExports.ov.scale = 2;
  pageExports.ovRender();
  byId['ovcv'].onclick({ clientX: 30, clientY: 50 });
  // 文本宽 58 高 14：点击居中于 (30,50) → ox=1, oy=43
  if (pageExports.ov.ox !== 1 || pageExports.ov.oy !== 43)
    fail(`经典点击定位错: ox=${pageExports.ov.ox} oy=${pageExports.ov.oy}`);
  byId['ovsc'].value = '1';
  byId['ovsc'].onchange();
  if (pageExports.ov.scale !== 1) fail('字号切换失效');
  byId['ovfg'].value = '1';                 // 黑字（浅底表盘用）
  byId['ovfg'].onchange();
  if (pageExports.ov.fg !== 1) fail('前景色切换失效');
  pageExports.ovNudge(1, 0);
  if (pageExports.ov.ox !== 2) fail('经典微调失效');
  calls.length = 0;
  byId['ovsave'].onclick();
  await sleep(30);
  const save2 = calls.find(c => c.url.startsWith('/dialov'));
  const q2 = new URL('http://x' + save2.url).searchParams;
  if (q2.get('mode') !== '0' || q2.get('ovs') !== '1' || q2.get('ox') !== '2' || q2.get('ovfg') !== '1')
    fail('经典模式保存参数错: ' + save2.url);
  console.log('[7] 经典模式定位/字号/前景色/保存 OK ->', save2.url);

  // ---- 9) dialInfo 文案 ----
  const t1 = pageExports.dialInfo(dials[0]);
  if (!t1.includes('方块时钟')) fail('dialInfo 缺方块时钟: ' + t1);
  console.log('[8] dialInfo OK:', JSON.stringify(t1));

  console.log('\n全部通过 ✅');
  process.exit(0);
})().catch(e => { console.error('FAIL 异步异常:', e.stack); process.exit(1); });
