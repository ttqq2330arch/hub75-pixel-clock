// ============================================================
// faces_web.h — 自动生成，勿手改！
// 由 tools/gen_faces_web.py 生成：
//   源数据 miniprogram/data/faces-index.json（6 表盘 x 4096 px）
//   格式 RGB565 小端 base64（与固件 face_remote blit 逐位一致）
//   STA 模式由 net.cpp 在 GET / 提供（网页版表盘推送器）
// ============================================================
#pragma once
#include <Arduino.h>

const char PUSH_PAGE[] PROGMEM = R"PWGL(

<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>像素时钟 · 表盘推送</title>
<style>
:root{--bg:#101014;--card:#1a1a20;--line:#2c2c36;--txt:#e8e8ec;--dim:#8a8a96;--acc:#ffb000;--ok:#2ecc71;--err:#e74c3c}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{background:var(--bg);color:var(--txt);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0 auto;padding:16px;max-width:600px}
h1{font-size:19px;color:var(--acc);margin:4px 0 2px}
.sub{font-size:12px;color:var(--dim);margin-bottom:6px;line-height:1.5}
.sec{font-size:13px;color:var(--dim);margin:18px 0 8px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.cell{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px;text-align:center;cursor:pointer;transition:transform .08s}
.cell:active{transform:scale(.94)}
.cell canvas{width:100%;image-rendering:pixelated;border-radius:6px;display:block;background:#000}
.cell .nm{font-size:12px;color:var(--dim);margin-top:6px}
.cell{position:relative}
.gear{position:absolute;top:4px;right:4px;width:26px;height:26px;border-radius:8px;border:1px solid var(--line);background:rgba(16,16,20,.82);color:var(--dim);font-size:14px;line-height:1;cursor:pointer;padding:0;z-index:2}
.gear:active{background:#282832;color:var(--acc)}
.row{display:flex;gap:8px;flex-wrap:wrap}
.btn{flex:1;min-width:64px;padding:11px 4px;border-radius:10px;background:var(--card);color:var(--txt);border:1px solid var(--line);font-size:13px;cursor:pointer}
.btn:active{background:#282832}
#mask{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;justify-content:center;padding:20px;z-index:9}
#mask.show{display:flex}
#ovmask{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;align-items:center;justify-content:center;padding:16px;z-index:10;overflow:auto}
#ovmask.show{display:flex}
#ovdlg{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;width:100%;max-width:340px}
#ovcv{width:min(256px,68vw);height:min(256px,68vw);image-rendering:pixelated;border-radius:10px;background:#000;display:block;margin:0 auto;cursor:crosshair;touch-action:none}
.mbtn{padding:9px 4px;border-radius:10px;background:var(--bg);color:var(--dim);border:1px solid var(--line);font-size:13px;cursor:pointer;flex:1}
.mbtn.sel{background:var(--acc);color:#111;font-weight:700;border-color:var(--acc)}
.dpad{display:grid;grid-template-columns:repeat(3,40px);grid-template-rows:repeat(3,36px);gap:4px;justify-content:center;margin:10px 0 4px}
.dpad button{background:var(--bg);color:var(--txt);border:1px solid var(--line);border-radius:8px;font-size:15px;cursor:pointer}
.dpad button:active{background:#282832}
.dpad .sp{visibility:hidden}
#dlg{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;width:100%;max-width:320px;text-align:center}
#big{width:min(256px,66vw);height:min(256px,66vw);image-rendering:pixelated;border-radius:10px;background:#000}
#dname{font-size:15px;margin-top:10px;color:var(--txt)}
.pbtn{width:100%;padding:13px;border:0;border-radius:10px;background:var(--acc);color:#111;font-size:15px;font-weight:700;margin-top:12px;cursor:pointer}
.pbtn:disabled{background:#4a4a52;color:#999}
#prog{height:6px;background:#2a2a33;border-radius:3px;margin-top:10px;overflow:hidden;display:none}
#prog div{height:100%;background:var(--acc);width:0;transition:width .15s}
#toast{position:fixed;left:50%;top:36px;transform:translateX(-50%);background:#23232c;border:1px solid var(--line);padding:10px 18px;border-radius:10px;font-size:13px;display:none;z-index:99;max-width:80vw}
</style>
</head>
<body>
<h1>◈ 像素时钟</h1>
<div class="sub" id="st">连接中…</div>
<div class="sub" style="color:#5a5a66">同一 WiFi 下用浏览器打开本页即可推送表盘，无需蓝牙 / 小程序</div>
<div class="sec">表盘商店（点一下 → 推送）</div>
<div class="grid" id="grid"></div>
<div class="sec">表盘斗图库（点一下 → 直上屏）<label class="sub" style="float:right;font-size:11px;color:#5a5a66;margin:0"><input id="dialsave" type="checkbox" checked> 存 flash 开机自启</label></div>
<div class="grid" id="dgrid"></div>
<div class="sec">固件表盘</div>
<div class="row" id="fwrow"></div>

<div class="sec">屏幕亮度</div>
<div class="card" style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px">
  <div class="row" style="align-items:center;gap:10px">
    <input type="range" id="bright" min="0" max="255" value="55" style="flex:1;accent-color:var(--acc)">
    <span id="brightval" style="min-width:44px;text-align:right;font-size:14px;color:var(--acc);font-weight:700">55</span>
  </div>
  <div class="row" style="margin-top:10px">
    <button class="btn" data-b="15">🌙 暗</button>
    <button class="btn" data-b="55">☀ 中</button>
    <button class="btn" data-b="120">🔆 亮</button>
    <button class="btn" data-b="200">💡 最亮</button>
  </div>
  <button class="btn" id="brightApply" style="margin-top:10px;width:100%;font-weight:700">✓ 应用亮度</button>
  <div class="sub" style="margin:8px 0 0">拖动滑块选好亮度后点「应用亮度」推送（或点预设一键应用）。改动才会下发，避免拖动时屏幕乱闪；断电自动保存。</div>
</div>

<div class="sec">屏幕旋转</div>
<div class="card" style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px">
  <div class="row">
    <button class="btn" data-r="0" id="rot0">↺ 0°</button>
    <button class="btn" data-r="1" id="rot1">↻ 90°</button>
    <button class="btn" data-r="2" id="rot2">↻ 180°</button>
    <button class="btn" data-r="3" id="rot3">↻ 270°</button>
  </div>
  <div class="sub" style="margin:8px 0 0">画面整体旋转（时钟、表盘、动画、文字一起转），立即生效并断电保存。按板子的安装方向选角度即可。</div>
</div>

<div class="sec">WiFi 切换</div>
<div class="card" style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px">
  <div class="sub" style="margin:0 0 8px">当前连接: <b id="wifiCur" style="color:var(--acc)">获取中…</b></div>
  <input id="wifiSsid" placeholder="新 WiFi 名称" style="width:100%;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--txt);font-size:14px;margin-bottom:8px">
  <div style="display:flex;gap:8px">
    <input id="wifiPass" type="password" placeholder="WiFi 密码" style="flex:1;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--txt);font-size:14px">
    <button class="btn" id="wifiGo" style="flex:0 0 auto;font-weight:700">📡 切换</button>
  </div>
  <div class="sub" style="margin:8px 0 0">点「切换」后板子<b>立即重启</b>去连新 WiFi（约 30 秒）。成功后把手机/电脑也连到新 WiFi 再访问；若连不上，板子会自动开配网热点 <b>PixelClock-Setup</b>（密码 12345678），不会失联。</div>
</div>

<div class="sec">动画背景（动漫像素时钟 · 存 flash 重启自动播）</div>
<div class="card" style="background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px">
  <div class="sub" id="animst" style="margin:0 0 8px">读取中…</div>
  <div class="row">
    <button class="btn" id="animload">▶ 播放存储的动画</button>
    <button class="btn" id="animsave">💾 存为开机动画</button>
  </div>
  <div class="row" style="margin-top:8px;align-items:center">
    <label class="sub" style="margin:0">帧率 <input id="fps" type="number" value="10" min="1" max="30" style="width:52px;background:var(--bg);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:4px 6px"></label>
    <label class="sub" style="margin:0"><input id="ovl" type="checkbox" checked> 叠加实时时钟</label>
  </div>
  <div style="margin-top:10px">
    <input type="file" id="animfile" accept=".rgb565,.bin" class="sub" style="font-size:12px">
    <button class="btn" id="animpush" style="margin-top:8px;width:100%">⬆ 上传 .rgb565 动画并播放</button>
  </div>
  <div id="aprog"><div></div></div>
</div>

<div id="mask"><div id="dlg">
  <canvas id="big" width="64" height="64"></canvas>
  <div id="dname"></div>
  <button class="pbtn" id="pbtn">推送到面板</button>
  <div id="prog"><div></div></div>
  <button class="btn" id="cbtn" style="margin-top:10px;width:100%">关闭</button>
</div></div>

<div id="ovmask"><div id="ovdlg">
  <div style="font-size:15px;color:var(--txt);margin-bottom:4px" id="ovtitle">时钟叠加层</div>
  <div class="sub" style="margin:0 0 10px">点画面设定时钟位置 · 方块模式画在问号块里</div>
  <canvas id="ovcv" width="64" height="64"></canvas>
  <div class="row" style="margin-top:10px">
    <button class="mbtn sel" id="ovm0">经典 HH:MM</button>
    <button class="mbtn" id="ovm1">方块数字</button>
  </div>
  <div class="row" style="margin-top:8px;align-items:center;justify-content:center">
    <span class="sub" id="ovpos" style="margin:0">x=12 y=11</span>
    <span class="sub" id="ovscw" style="margin:0 0 0 12px">字号
      <select id="ovsc" style="background:var(--bg);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:3px 6px">
        <option value="1">1</option><option value="2" selected>2</option>
      </select>
    </span>
    <span class="sub" id="ovfgw" style="margin:0 0 0 12px">颜色
      <select id="ovfg" style="background:var(--bg);color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:3px 6px">
        <option value="0" selected>白</option><option value="1">黑</option><option value="2">黄</option>
      </select>
    </span>
  </div>
  <div class="dpad">
    <button class="sp"></button><button id="ovup">↑</button><button class="sp"></button>
    <button id="ovleft">←</button><button id="ovreset">⟲</button><button id="ovright">→</button>
    <button class="sp"></button><button id="ovdown">↓</button><button class="sp"></button>
  </div>
  <button class="pbtn" id="ovsave">保存到设备</button>
  <button class="btn" id="ovclose" style="margin-top:8px;width:100%">关闭</button>
</div></div>
<div id="toast"></div>

<script>
var FACES = [];
var DIALS = [];
var FW = [{i:0,n:'TEST'},{i:1,n:'CLOCK'},{i:2,n:'PLASMA'},{i:3,n:'REMOTE'}];

function b64ToU8(b64){
  var bin = atob(b64), u8 = new Uint8Array(bin.length);
  for (var i=0;i<bin.length;i++) u8[i] = bin.charCodeAt(i);
  return u8;
}
function drawFace(cv, u8){
  var ctx = cv.getContext('2d');
  var img = ctx.createImageData(64,64);
  for (var i=0;i<4096;i++){
    var c = u8[i*2] | (u8[i*2+1]<<8);
    img.data[i*4]   = Math.round(((c>>11)&0x1f)*255/31);
    img.data[i*4+1] = Math.round(((c>>5)&0x3f)*255/63);
    img.data[i*4+2] = Math.round((c&0x1f)*255/31);
    img.data[i*4+3] = 255;
  }
  ctx.putImageData(img,0,0);
}
function toHex(u8, from, to){
  var p = [];
  for (var i=from;i<to;i++) p.push(u8[i].toString(16).padStart(2,'0'));
  return p.join('');
}
var toastT = null;
function toast(msg, ms){
  var t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  if (toastT) clearTimeout(toastT);
  toastT = setTimeout(function(){ t.style.display='none'; }, ms||2200);
}

// ---- 表盘商店网格（数据来自 /faces，按需拉取带重试；首页不再内嵌预览，MIN_MODEM 下更稳定）----
// v0.3.15：控制面板本体精简到 <5KB（FACES/DIALS 占位符注入为空），
// 6 个表盘的预览图改由设备 /faces 端点 gzip 下发，掉一两次自动重来，不影响主控制面板。
var grid = document.getElementById('grid');
function buildFaceGrid(faces){
  grid.innerHTML = '';
  faces.forEach(function(f){
    var cell = document.createElement('div');
    cell.className = 'cell';
    var cv = document.createElement('canvas');
    cv.width = 64; cv.height = 64;
    cell.appendChild(cv);
    var nm = document.createElement('div');
    nm.className = 'nm'; nm.textContent = f.n;
    cell.appendChild(nm);
    cell.onclick = function(){ openDlg(f); };
    grid.appendChild(cell);
    drawFace(cv, b64ToU8(f.d));
  });
}
function loadFaces(){
  grid.innerHTML = '<div class="sub" style="grid-column:1/-1;color:#8a8a96">表盘商店加载中…</div>';
  fetchRetry('/faces', 6, 1800)
    .then(function(j){
      FACES = j;                 // 回填全局，openDlg/pushFace 才能拿到 f.d
      buildFaceGrid(j);
    })
    .catch(function(){
      grid.innerHTML = '<div class="sub" style="grid-column:1/-1;color:#8a8a96">' +
        '表盘商店加载失败（<a href="javascript:loadFaces()" style="color:var(--acc)">点此重试</a>）</div>';
    });
}
loadFaces();

// ---- 表盘斗图库（FS 版：列表/缩略图/播放走设备 LittleFS，数量不受固件体积限制）----
// 一键序列：POST /dialplay（设备从 FS 载入并播放）→ 可选 /animsave 存 flash
var dgrid = document.getElementById('dgrid');

function dialInfo(d){
  var base = d.b ? (d.c + '帧 · 整分钟顶金币') :
    (d.c > 1 ? (d.c + '帧 @' + d.f + 'fps') : '静态');
  if (d.o) base += (d.m === 1) ? ' · 方块时钟' : ' · 时钟';
  return base;
}

// 缩略图队列：设备 WebServer 单客户端，43 个并发会把连接挤爆，限 3 个一批
var thumbQueue = [], thumbRunning = 0;
function pumpThumbs(){
  while (thumbRunning < 3 && thumbQueue.length){
    var job = thumbQueue.shift();
    thumbRunning++;
    fetch('/dialpreview?name=' + encodeURIComponent(job[1]))
      .then(function(r){ return r.text(); })
      .then(function(b64){
        var bin = atob(b64);
        var cv = document.createElement('canvas'); cv.width = 64; cv.height = 64;
        var ctx = cv.getContext('2d');
        var id = ctx.createImageData(64, 64);
        for (var i = 0; i < 4096; i++){
          var c = bin.charCodeAt(i*2) | (bin.charCodeAt(i*2+1) << 8);
          id.data[i*4]   = ((c >> 11) & 0x1F) * 255 / 31;
          id.data[i*4+1] = ((c >> 5) & 0x3F) * 255 / 63;
          id.data[i*4+2] = (c & 0x1F) * 255 / 31;
          id.data[i*4+3] = 255;
        }
        ctx.putImageData(id, 0, 0);
        job[0].src = cv.toDataURL();
      })
      .catch(function(){})
      .then(function(){ thumbRunning--; pumpThumbs(); });
  }
}
function enqueueThumb(img, name){
  thumbQueue.push([img, name]);
  pumpThumbs();
}

function loadDialGallery(){
  fetch('/diallist')
    .then(function(r){ return r.json(); })
    .then(function(j){
      dgrid.innerHTML = '';
      (j.dials || []).forEach(function(d){
        var cell = document.createElement('div');
        cell.className = 'cell';
        var img = document.createElement('img');
        img.style.cssText = 'width:100%;image-rendering:pixelated;border-radius:6px;background:#000';
        cell.appendChild(img);
        var nm = document.createElement('div');
        nm.className = 'nm'; nm.textContent = d.n;
        cell.appendChild(nm);
        var info = document.createElement('div');
        info.className = 'sub';
        info.style.cssText = 'font-size:10px;color:#5a5a66;margin:0';
        info.textContent = dialInfo(d);
        cell.appendChild(info);
        var gear = document.createElement('button');
        gear.className = 'gear'; gear.textContent = '⚙'; gear.title = '调整时钟位置';
        gear.onclick = function(e){ e.stopPropagation(); openOv(d); };
        cell.appendChild(gear);
        var del = document.createElement('button');
        del.className = 'gear'; del.textContent = '🗑'; del.title = '删除表盘';
        del.style.right = '34px';
        del.onclick = function(e){ e.stopPropagation(); deleteDial(d.n); };
        cell.appendChild(del);
        cell.onclick = function(){ pushFsDial(d); };
        dgrid.appendChild(cell);
        enqueueThumb(img, d.n);
      });
      if (!(j.dials || []).length) {
        dgrid.innerHTML = '<div class="sub" style="grid-column:1/-1;color:#8a8a96">FS 里还没有表盘，先用下面的上传按钮推一个</div>';
      }
    })
    .catch(function(e){ toast('表盘库加载失败: ' + e.message); });
}

function pushFsDial(d){
  var save = document.getElementById('dialsave').checked;
  toast('切换「' + d.n + '」…', 10000);
  fetch('/dialplay?name=' + encodeURIComponent(d.n), {method:'POST'})
    .then(function(r){
      if (!r.ok) throw new Error('HTTP ' + r.status);
      animPoll();
      toast('✓ 已上屏「' + d.n + '」', 3000);
      if (!save) return null;
      return fetch('/animsave', {method:'POST'});
    })
    .then(function(){
      if (save) toast('✓ 已存 flash（重启自动播）', 3000);
    })
    .catch(function(e){ toast('✗ ' + e.message); });
}

// ---- 删除表盘（FS：删 .rgb565 + .json，不可恢复）----
function deleteDial(name){
  if (!confirm('确定删除表盘「' + name + '」？\n文件将从设备 flash 删除，不可恢复。')) return;
  toast('删除「' + name + '」…', 8000);
  fetch('/dialdel?name=' + encodeURIComponent(name), {method:'POST'})
    .then(function(r){ return r.text().then(function(t){ return {ok:r.ok, t:t}; }); })
    .then(function(j){
      if (!j.ok) throw new Error(j.t || ('HTTP ' + j.t));
      toast('✓ 已删除「' + name + '」', 3000);
      loadDialGallery();   // 刷新列表
    })
    .catch(function(e){ toast('✗ ' + e.message); });
}

// ---- 叠加层调整：时钟位置/模式（经典 HH:MM ↔ 方块数字）----
// 7x7 马里奥字体（与固件 kGlyph7 一致，'#'=墨点）
var GLYPH7 = [
  ['.#####.','##..###','##..###','##..###','##..###','##..###','.#####.'],
  ['..###..','.####..','..###..','..###..','..###..','..###..','.#####.'],
  ['.#####.','##..###','....###','..####.','.###...','###....','#######'],
  ['.######','....##.','..###..','....##.','....###','##..###','.#####.'],
  ['...###.','..####.','.##.##.','##..##.','#######','....##.','....##.'],
  ['######.','##.....','######.','....###','....###','##..###','.#####.'],
  ['.#####.','##.....','######.','##..###','##..###','##..###','.#####.'],
  ['#######','##..###','....##.','...##..','..##...','..##...','..##...'],
  ['.#####.','##..###','##..###','.#####.','##..###','##..###','.#####.'],
  ['.#####.','##..###','##..###','.######','....###','....###','.#####.']
];
var OVFG_CSS = ['#fff','#000','#ff0'];
var ov = { name:'', mode:0, ox:-1, oy:46, ox2:34, scale:2, fg:0, frame:null };

function ovInkB(d){ var f=7,l=0; for(var r=0;r<7;r++) for(var c=0;c<7;c++) if(GLYPH7[d][r][c]==='#'){ if(c<f)f=c; if(c>l)l=c; } return [f,l]; }
function ovGlyph(ctx,x,y,d){ for(var r=0;r<7;r++) for(var c=0;c<7;c++) if(GLYPH7[d][r][c]==='#') ctx.fillRect(x+c,y+r,1,1); }
// 与固件 drawBlockDigits 相同的排版：墨点居中，间距 8（奇数补偿 9）
function ovBlock(ctx,bx,by,val){
  var t=Math.floor(val/10), u=val%10, a=ovInkB(t), b=ovInkB(u), n=19, pitch=8;
  if ((n-(pitch+b[1]-a[0]+1))%2) pitch=9;
  var start=(n-(pitch+b[1]-a[0]+1))/2-a[0];
  ctx.fillStyle='#e69d20'; ctx.fillRect(bx+1,by+6,17,7);   // 数字带填块体色
  ctx.fillStyle='#000';
  ovGlyph(ctx,bx+start,by+6,t); ovGlyph(ctx,bx+start+pitch,by+6,u);
}
function ovRender(){
  var cv=document.getElementById('ovcv'), ctx=cv.getContext('2d');
  ctx.fillStyle='#000'; ctx.fillRect(0,0,64,64);
  if (ov.frame) drawFace(cv, ov.frame);
  var now=new Date(), hh=now.getHours(), mm=now.getMinutes();
  if (ov.mode===1){
    if (ov.ox>=0&&ov.oy>=0)  ovBlock(ctx,ov.ox,ov.oy,hh);
    if (ov.ox2>=0&&ov.oy>=0) ovBlock(ctx,ov.ox2,ov.oy,mm);
  } else {
    var s=ov.scale, w=5*6*s-s, h=7*s;
    var x=(ov.ox<0)?Math.round((64-w)/2):ov.ox, y=ov.oy;
    var fg=OVFG_CSS[ov.fg]||'#fff';
    var ol=(ov.fg===1)?'#fff':((ov.fg===2)?'#000':'#000');
    // 反色描边（黑字白描边/白字黄字黑描边）
    ctx.fillStyle=ol;
    ctx.fillRect(x-1,y,w+2,1); ctx.fillRect(x-1,y+h,w+2,1);
    ctx.fillRect(x-1,y,1,h);   ctx.fillRect(x+w,y,1,h);
    ctx.fillStyle=fg; ctx.fillRect(x,y,w,h);
    ctx.fillStyle=ol; ctx.font='bold '+(h-2)+'px monospace';
    ctx.textAlign='center'; ctx.textBaseline='middle';
    ctx.fillText('12:34', x+w/2, y+h/2+1);
    ctx.fillStyle='#ff0'; ctx.fillRect(0,62,64,2);   // 秒进度条
  }
}
function ovShowPos(){
  var t='x='+((ov.mode===1)?ov.ox:((ov.ox<0)?'中':ov.ox))+' y='+ov.oy;
  if (ov.mode===1) t+=' · 分钟块 x='+ov.ox2;
  document.getElementById('ovpos').textContent=t;
}
function ovSyncBtns(){
  document.getElementById('ovm0').classList.toggle('sel', ov.mode===0);
  document.getElementById('ovm1').classList.toggle('sel', ov.mode===1);
  document.getElementById('ovsc').value=ov.scale;
  document.getElementById('ovfg').value=ov.fg;
  document.getElementById('ovscw').style.display=(ov.mode===0)?'':'none';
  document.getElementById('ovfgw').style.display=(ov.mode===0)?'':'none';
}
function openOv(d){
  ov.name=d.n; ov.mode=d.m||0;
  ov.ox =(d.x===undefined)?-1:d.x;  ov.oy=(d.y===undefined)?46:d.y;
  ov.ox2=(d.x2===undefined)?34:d.x2; ov.scale=d.sc||2; ov.fg=d.fg||0;
  document.getElementById('ovtitle').textContent='「'+d.n+'」时钟叠加层';
  ovSyncBtns(); ovShowPos();
  fetch('/dialpreview?name='+encodeURIComponent(d.n))
    .then(function(r){ return r.text(); })
    .then(function(b64){ ov.frame=b64ToU8(b64); ovRender(); })
    .catch(function(){ ov.frame=null; ovRender(); });
  document.getElementById('ovmask').classList.add('show');
}
document.getElementById('ovclose').onclick=function(){ document.getElementById('ovmask').classList.remove('show'); };
document.getElementById('ovm0').onclick=function(){ ov.mode=0; ovSyncBtns(); ovRender(); ovShowPos(); };
document.getElementById('ovm1').onclick=function(){ ov.mode=1; ovSyncBtns(); ovRender(); ovShowPos(); };
document.getElementById('ovsc').onchange=function(){ ov.scale=parseInt(this.value)||2; ovRender(); ovShowPos(); };
document.getElementById('ovfg').onchange=function(){ ov.fg=parseInt(this.value)||0; ovRender(); ovShowPos(); };
document.getElementById('ovcv').onclick=function(e){
  var r=this.getBoundingClientRect();
  var x=Math.round((e.clientX-r.left)/r.width*64);
  var y=Math.round((e.clientY-r.top)/r.height*64);
  if (ov.mode===1){
    ov.ox =Math.max(0,Math.min(45,x)); ov.oy=Math.max(0,Math.min(45,y));
    ov.ox2=Math.max(0,Math.min(45,ov.ox+22));
  } else {
    var s=ov.scale, w=5*6*s-s, h=7*s;
    ov.ox =Math.max(0,Math.min(64-w,x-Math.round(w/2)));
    ov.oy =Math.max(0,Math.min(64-h,y-Math.round(h/2)));
  }
  ovRender(); ovShowPos();
};
function ovNudge(dx,dy){
  if (ov.mode===1){
    if (dx){ ov.ox=Math.max(0,Math.min(45,ov.ox+dx)); ov.ox2=Math.max(0,Math.min(45,ov.ox2+dx)); }
    if (dy){ ov.oy=Math.max(0,Math.min(45,ov.oy+dy)); }
  } else {
    var s=ov.scale, w=5*6*s-s, h=7*s;
    if (ov.ox<0) ov.ox=Math.round((64-w)/2);
    ov.ox=Math.max(0,Math.min(64-w,ov.ox+dx));
    ov.oy=Math.max(0,Math.min(64-h,ov.oy+dy));
  }
  ovRender(); ovShowPos();
}
document.getElementById('ovup').onclick   =function(){ ovNudge(0,-1); };
document.getElementById('ovdown').onclick =function(){ ovNudge(0, 1); };
document.getElementById('ovleft').onclick =function(){ ovNudge(-1,0); };
document.getElementById('ovright').onclick=function(){ ovNudge( 1,0); };
document.getElementById('ovreset').onclick=function(){
  if (ov.mode===0){ ov.ox=-1; ov.oy=46; ov.scale=2; ov.fg=0; }
  else { ov.ox=12; ov.oy=11; ov.ox2=34; }
  ovSyncBtns(); ovRender(); ovShowPos();
};
document.getElementById('ovsave').onclick=function(){
  var q='/dialov?name='+encodeURIComponent(ov.name)+'&mode='+ov.mode+
        '&ox='+ov.ox+'&oy='+ov.oy+'&ox2='+ov.ox2+'&ovs='+ov.scale+'&ovfg='+ov.fg;
  fetch(q,{method:'POST'})
    .then(function(r){ return r.text().then(function(t){
      toast(r.ok?'✓ 叠加层已保存，下一帧生效':'✗ '+t, 2500);
      if (r.ok) loadDialGallery();
    }); })
    .catch(function(e){ toast('✗ '+e.message); });
};

loadDialGallery();

// ---- 固件表盘按钮 ----
var fwrow = document.getElementById('fwrow');
FW.forEach(function(f){
  var b = document.createElement('button');
  b.className = 'btn'; b.textContent = f.n;
  b.onclick = function(){
    fetch('/face?idx='+f.i, {method:'POST'})
      .then(function(r){ toast(r.ok ? '✓ 已切换到 '+f.n : '✗ 切换失败'); })
      .catch(function(e){ toast('✗ '+e.message); });
  };
  fwrow.appendChild(b);
});

// ---- 推送对话框 ----
var mask = document.getElementById('mask');
var pbtn = document.getElementById('pbtn');
var prog = document.getElementById('prog');
var progBar = prog.firstChild;
function openDlg(f){
  document.getElementById('dname').textContent = f.n;
  drawFace(document.getElementById('big'), b64ToU8(f.d));
  prog.style.display = 'none'; progBar.style.width = '0';
  pbtn.disabled = false; pbtn.textContent = '推送到面板';
  pbtn.onclick = function(){ pushFace(f); };
  mask.classList.add('show');
}
document.getElementById('cbtn').onclick = function(){ mask.classList.remove('show'); };
mask.onclick = function(e){ if (e.target === mask) mask.classList.remove('show'); };

function pushFace(f){
  var u8 = b64ToU8(f.d);
  var CH = 1024, off = 0;
  pbtn.disabled = true; pbtn.textContent = '推送中…';
  prog.style.display = 'block';
  function step(){
    if (off >= u8.length){
      fetch('/pushface?commit=1', {method:'POST'})
        .then(function(r){ return r.text().then(function(t){ return {ok:r.ok, t:t}; }); })
        .then(function(j){
          if (!j.ok) throw new Error(j.t || ('HTTP '+j.t));
          progBar.style.width = '100%';
          pbtn.textContent = '✓ 已推送';
          toast('✓ 已推送「'+f.n+'」，面板已切换');
          setTimeout(function(){ mask.classList.remove('show'); }, 900);
        })
        .catch(function(e){
          pbtn.disabled = false; pbtn.textContent = '重试推送';
          toast('✗ 提交失败：'+e.message);
        });
      return;
    }
    var end = Math.min(off+CH, u8.length);
    fetch('/pushface?off='+off+'&len='+(end-off), {method:'POST', body: toHex(u8, off, end)})
      .then(function(r){
        if (!r.ok) throw new Error('分片 '+off+' HTTP '+r.status);
        off = end;
        progBar.style.width = (off/u8.length*100)+'%';
        step();
      })
      .catch(function(e){
        pbtn.disabled = false; pbtn.textContent = '重试推送';
        toast('✗ '+e.message);
      });
  }
  step();
}

// ---- 状态轮询 ----
// 固件 WebServer 是单客户端的：Python 脚本推送动画的几秒内轮询会被拒，
// 误报"无法连接设备"。fetchRetry 失败后自动重试（4 次 x 2s，覆盖最长推送窗口），
// 仍失败才提示，且提示语说明"可能正在推送"而非让用户误查 WiFi。
var st = document.getElementById('st');
function fetchRetry(url, tries, delayMs){
  return fetch(url, {cache:'no-store'}).then(function(r){
    if (!r.ok) throw new Error('HTTP '+r.status);
    return r.json();
  }).catch(function(e){
    if (tries <= 1) throw e;
    return new Promise(function(res){ setTimeout(res, delayMs); })
      .then(function(){ return fetchRetry(url, tries-1, delayMs); });
  });
}
function poll(){
  fetchRetry('/status', 4, 2000)
    .then(function(j){
      st.textContent = j.ip + ' · 信号 '+j.rssi+'dBm · 推送状态 '+j.push;
    })
    .catch(function(){ st.textContent = '⏳ 设备无响应（可能正在推送动画，请稍候）'; });
  setTimeout(poll, 10000);
}
poll();

// ---- 动画背景 ----
var animst = document.getElementById('animst');
var aprog = document.getElementById('aprog');
var aprogBar = aprog.firstChild;
aprog.style.cssText = 'height:6px;background:#2a2a33;border-radius:3px;margin-top:10px;overflow:hidden;display:none';

function animPoll(){
  fetchRetry('/animlist', 3, 1500)
    .then(function(j){
      animst.textContent = '动画缓冲：' + j.frames + ' 帧 · ' + j.fps + 'fps · 时钟叠加 ' +
        (j.overlay ? '开' : '关') + ' · 上限 ' + j.cap + ' 帧 · flash ' + (j.fs ? '有存档' : '无');
    })
    .catch(function(){ animst.textContent = '⚠ 动画状态读取失败'; });
}
animPoll();
setInterval(animPoll, 15000);   // 周期刷新：Python 侧换了动画后页面 15s 内自动跟上

document.getElementById('animload').onclick = function(){
  fetch('/animload', {method:'POST'})
    .then(function(r){ return r.text().then(function(t){ animPoll(); toast(r.ok ? '▶ '+t : '✗ '+t); }); })
    .catch(function(e){ toast('✗ '+e.message); });
};
document.getElementById('animsave').onclick = function(){
  fetch('/animsave', {method:'POST'})
    .then(function(r){ return r.text().then(function(t){ animPoll(); toast(r.ok ? '💾 '+t : '✗ '+t); }); })
    .catch(function(e){ toast('✗ '+e.message); });
};

// 上传 .rgb565（帧数 = 文件大小 / 8192），分帧分块 hex 推送
document.getElementById('animpush').onclick = function(){
  var fileInput = document.getElementById('animfile');
  if (!fileInput.files.length){ toast('先选 .rgb565 文件'); return; }
  var file = fileInput.files[0];
  if (file.size % 8192 !== 0){ toast('✗ 文件大小须为 8192 的倍数'); return; }
  var fps  = parseInt(document.getElementById('fps').value) || 10;
  var ovl  = document.getElementById('ovl').checked ? 1 : 0;
  var rd = new FileReader();
  rd.onload = function(){
    var u8 = new Uint8Array(rd.result);
    var nFrames = u8.length / 8192;
    var CH = 1024, fi = 0, off = 0, total = u8.length;
    aprog.style.display = 'block'; aprogBar.style.width = '0';
    function step(){
      if (fi >= nFrames){
        fetch('/anim?frames='+nFrames+'&fps='+fps+'&overlay='+ovl, {method:'POST'})
          .then(function(r){ return r.text().then(function(t){
              aprogBar.style.width = '100%';
              animPoll();
              toast(r.ok ? '✓ '+t+'（'+nFrames+' 帧 @'+fps+'fps）' : '✗ '+t);
            }); })
          .catch(function(e){ toast('✗ '+e.message); });
        return;
      }
      if (off >= 8192){ fi++; off = 0; return step(); }
      var end = Math.min(off+CH, 8192);
      var absOff = fi*8192 + off;
      fetch('/pushface?off='+absOff+'&len='+(end-off), {method:'POST', body: toHex(u8, absOff, absOff+(end-off))})
        .then(function(r){
          if (!r.ok) throw new Error('分片 '+absOff+' HTTP '+r.status);
          off = end;
          aprogBar.style.width = ((fi*8192+off)/total*100)+'%';
          step();
        })
        .catch(function(e){ toast('✗ '+e.message); aprog.style.display = 'none'; });
    }
    step();
  };
  rd.readAsArrayBuffer(file);
};

// ---- 屏幕亮度 ----
// GET /brightness → {"level":N} 当前目标亮度；POST /brightness?level=N → 设置并持久化
// 注意：拖动滑块【不会】实时下发，必须点「应用亮度」或预设才会推送，避免拖动时屏闪。
var bright = document.getElementById('bright');
var brightval = document.getElementById('brightval');
var brightApply = document.getElementById('brightApply');
function applyBright(v){
  v = Math.max(0, Math.min(255, v|0));
  fetch('/brightness?level=' + v, {method:'POST'})
    .then(function(r){ return r.text().then(function(t){
      toast(r.ok ? ('✓ 亮度已设为 ' + v) : ('✗ ' + t));
    }); })
    .catch(function(e){ toast('✗ ' + e.message); });
}
// 拖动只更新数字显示，不发包
bright.addEventListener('input', function(){ brightval.textContent = bright.value; });
// 预设：一键填值并立即应用（点一下即"确认"，属有意操作）
document.querySelectorAll('[data-b]').forEach(function(btn){
  btn.onclick = function(){
    var v = parseInt(btn.getAttribute('data-b'));
    bright.value = v; brightval.textContent = v; applyBright(v);
  };
});
// 应用按钮：把滑块当前值推送到面板
brightApply.onclick = function(){ applyBright(parseInt(bright.value)); };
// 初始化：拉取设备当前亮度回填滑块（只读，不下发）
fetchRetry('/brightness', 4, 2000)
  .then(function(j){ bright.value = j.level; brightval.textContent = j.level; })
  .catch(function(){});

// ---- 屏幕旋转（v0.3.22）----
// POST /rotate?v=0..3 → 指定角度；GET /rotate → 循环切换。返回 {"rot":N,"deg":N*90}
function setRot(v){
  fetch('/rotate?v=' + v, {method:'POST'})
    .then(function(r){ return r.text().then(function(t){
      if (r.ok) { toast('✓ 已旋转到 ' + JSON.parse(t).deg + '°'); markRot(v); }
      else toast('✗ ' + t);
    }); })
    .catch(function(e){ toast('✗ ' + e.message); });
}
function markRot(v){
  document.querySelectorAll('[data-r]').forEach(function(b){
    var sel = parseInt(b.getAttribute('data-r')) === v;
    b.style.borderColor = sel ? 'var(--acc)' : '';
    b.style.color       = sel ? 'var(--acc)' : '';
    b.style.fontWeight  = sel ? '700' : '';
  });
}
document.querySelectorAll('[data-r]').forEach(function(btn){
  btn.onclick = function(){ setRot(parseInt(btn.getAttribute('data-r'))); };
});
fetchRetry('/status', 4, 2000)
  .then(function(j){ if (typeof j.rot === 'number') markRot(j.rot); })
  .catch(function(){});

// ---- WiFi 切换（v0.3.23）----
// GET /wifi → {"ssid":"xx"}；POST /wifi?ssid=&pass= → 保存并重启（失败自动回配网热点）
var wifiGo = document.getElementById('wifiGo');
fetchRetry('/wifi', 4, 2000)
  .then(function(j){ document.getElementById('wifiCur').textContent = j.ssid || '未知'; })
  .catch(function(){ document.getElementById('wifiCur').textContent = '未知'; });
wifiGo.onclick = function(){
  var s = document.getElementById('wifiSsid').value.trim();
  var p = document.getElementById('wifiPass').value;
  if (!s) { toast('✗ 请填写新 WiFi 名称'); return; }
  if (p && p.length < 8) { toast('✗ 密码至少 8 位（开放网络请留空）'); return; }
  if (!window.confirm('切换到「' + s + '」？\n板子将立即重启，本页随后不可用。')) return;
  wifiGo.disabled = true; wifiGo.textContent = '重启中…';
  fetch('/wifi?ssid=' + encodeURIComponent(s) + '&pass=' + encodeURIComponent(p), {method:'POST'})
    .then(function(r){ return r.text().then(function(t){
      if (r.ok) {
        alert('已下发，板子正在重启并连接「' + s + '」。\n\n✅ 连接成功：把手机/电脑也连到新 WiFi，再访问新 IP。\n\n⚠️ 连接失败：板子会自动开配网热点 PixelClock-Setup（密码 12345678），连上后打开 http://192.168.4.1 重新配网即可，板子不会失联。');
      } else { toast('✗ ' + t); wifiGo.disabled = false; wifiGo.textContent = '📡 切换'; }
    }); })
    .catch(function(e){ toast('（板子已重启，属正常）'); });
};
</script>
</body>
</html>


)PWGL";
