# -*- coding: utf-8 -*-
"""
gen_board.py — HUB75 转接板 v2.2（ESP32-S3-DevKitC-1 帽子板 → HUB75 64x64）

★ v2.1 相对 v2.0 的关键修正（P0 机械错误 —— v2.0 的 pin1 位置偏差 0.4mm）：
  v2.0 用「圆弧反解圆心」估算焊盘位置，误差 0.1~0.6mm，导致排母整体错位、插不进模组。
  v2.1 改用**官方图纸丝印编号文本坐标**作为焊盘中心锚点（纯文本坐标，4 位小数内自洽），
  并经三重交叉验证：
     ① 丝印编号坐标  ② 图纸蓝色尺寸线箭头端点  ③ (25.40-22.86)/2 公式
  定案几何（相对 DevKitC-1 板框左上角，单位 mm）：
     板 25.40 × 62.74 ；J1 x=1.2700 ；J3 x=24.1300 ；排距 22.8600
     pin1 y = 1.8794 ；针距 2.5400 ；pin22 y = 55.2194
     ★ pin1 在天线/模组端（板顶），pin22 在 USB/UART 端（板底）

★ v2.2 相对 v2.1 的关键修正（P0 工艺错误 —— 丝印不满足嘉立创字符生产下限）：
  嘉立创官方《字符设计规范》（jlcpcb.com/blog/character-design-specifications）：
     常规字体：字符线宽 ≥ 0.15mm，**字符高度 ≥ 1.0mm**（高精字符 0.8mm）
     字符距焊盘 ≥ 0.15mm（推荐 ≥ 0.25mm）；字符间隙 > 0.15mm
     ★「若小于本参数…可能导致字符严重不清楚…公司不接受此类投诉」
  v2.1 全部丝印用 0.45~0.95mm 高度 + 0.08~0.16mm 线宽 → **线上打样会整片糊字**，
  其中 J2 针序对照表是本板唯一能防"排线插反"的信息，必须 1.0mm 重排。
  v2.2 改动：
     ① 全部字符高度 ≥ 1.0mm、线宽 ≥ 0.15mm
     ② 删除 J1/J3 逐脚序号（1.0mm 字高在 1.47mm 板边距内放不下；
        且 DevKit 模组自身已印有脚号，插上后仍可见 → 冗余）
     ③ J2 对照表改双栏（ODD/EVEN 分栏，行与 J2 焊盘行一一对齐）
     ④ 板宽 40.0 → 44.0mm，为 1.0mm 字高的表格腾出右侧空间
     ⑤ DevKit 轮廓说明文字移到 F.Fab 装配层（原丝印会被模组盖住且压焊盘）

★ 载板板高定案 H = 54.5：
  官方图纸底部 8.00mm 标注 = 板底带 y 54.864..62.865；两个 USB-C 座
  （x 2.25..9.75 与 x 15.64..23.14）凸出到 y = 63.72。
  ⇒ 载板底边必须 < 54.864，否则挡住 USB 插头。取 54.5（余量 0.36mm）。
  ⇒ 本板只焊 1..21 脚（pin22 在 USB 区上方，不焊），DevKit 的 GND 由 J3-21 引入。

★ HUB75 侧针序 = 用户现有旧转接板 J1 的针序（= 屏标准序「奇偶脚两两互换」）：
  该组合已被用户实测验证（屏正常显示），因此 —— 用户排线插法不用改、固件 config.h 零改动。

本脚本只生成「空板 + 焊盘 + 网络 + 丝印 + 板框 + B.Cu GND 铺铜」，布线由 Freerouting 完成。
"""
import math
import pcbnew
from pcbnew import (VECTOR2I, PCB_SHAPE, SHAPE_T_SEGMENT, SHAPE_T_ARC,
                    PCB_TEXT, FOOTPRINT, PAD, ZONE, NETINFO_ITEM, LIB_ID,
                    SHAPE_POLY_SET)

NM = 1_000_000


def mm(v):
    return int(round(v * NM))


# ================= 板参数 =================
W, H = 44.0, 54.5           # 板框中心线尺寸 mm（右侧留 17.6mm 扩展区：HUB75 + I2C + UART + 丝印）
RC = 3.0                    # 圆角半径
OUTLINE_W = 0.1
PAD_D, DRILL = 1.6, 1.0     # 2.54 排母/排针 焊盘 / 钻孔
PITCH = 2.54

# ---- 丝印工艺下限（嘉立创常规字体）----
SILK_MIN_H = 1.0            # 字符高度下限 mm
SILK_MIN_T = 0.15           # 字符线宽下限 mm
SILK_PAD_KEEP = 0.30        # 字符距焊盘推荐间距 mm
SILK_EDGE_KEEP = 0.40       # 字符距板框安全距离 mm

# ---- DevKitC-1 落位（官方实测，见 F:/AI数据/2026-10-15-15-57-08/devkit_geom.py）----
# 数据源：官方 PCB_ESP32-S3-DevKitC-1_V1_20210312CB.pdf
#   提取每个排针焊盘旁的丝印编号文本坐标 → 焊盘中心
#   比例尺：板宽 25.40mm（黄线轮廓 x 168.312..391.418 pt）
# 三重交叉验证：丝印坐标 / 图纸「1.27mm」箭头端点 / (25.40-22.86)/2 公式 —— 全部吻合
DK_LEFT = 1.0               # DevKitC-1 左边缘在本板上的 x
DK_TOP = 0.0                # DevKitC-1 上边缘（天线/模组端）在本板上的 y
DK_EDGE_TO_PIN = 1.2700     # 排针中心到板边（官方标注 1.27mm）
J1_X = DK_LEFT + DK_EDGE_TO_PIN          # 2.2700
ROW_GAP = 22.8600                         # 两排中心距（0.9"）
J3_X = J1_X + ROW_GAP                     # 25.1300
DK_RIGHT = J3_X + DK_EDGE_TO_PIN          # 26.4000
PIN1_Y = DK_TOP + 1.8794                  # pin1 中心距 DevKit 板顶边 1.8794mm ← 官方实测
NPIN = 21                                 # 本板只焊到 21 脚（pin22 在 USB 区上方，不焊）

# ---- 天线净空（ESP32-S3-WROOM-1 天线区）----
# ★ v2.4 重大修正（依据官方图纸实测，推翻 v2.2/v2.3 的 6.5mm 保守值）：
#   官方 PCB 图纸 PDF（devkit_pcb_layout.pdf）实测只有 4 条关键图形：
#     黄色 板框      x[0.00, 25.40]  y[0.00, 62.86]
#     红色 铜层边界  x[0.20, 25.19]  y[0.20, 62.66]
#     灰色 天线区    x[3.75, 21.75]  y[-6.27, 0.52]   ← 关键
#   灰色矩形宽 18.00mm = 模块宽度 ⇒ 它就是 ESP32-S3-WROOM-1 的天线区，
#   且**主体在 y<0，即悬出 DevKit 板顶边 6.27mm**，只有 0.52mm 搭进板内。
#   ⇒ 模块是「悬出板边、天线朝板外」的摆法（Espressif 官方推荐），
#     天线位于自由空间，**不在 DevKit 自身铜箔正下方**。
#
#   我们的载板：DevKit 顶边与载板顶边齐平（DK_TOP = 0），
#     模块天线再往上伸出 6.27mm ⇒ 天线落在**载板顶边之外**，
#     载板铜箔不在天线正下方 ⇒ 无需 6.5mm 深净空！
#
#   载板真正需要避让的，只有天线的**垂直投影带**：
#     天线区 y[-6.27, 0.52] ∩ 载板(y≥0) = y[0, 0.52]
#   ⇒ 规则区取 x[4.55, 22.95]、y[-1.0, 0.80]（各留 0.2~0.28mm 裕量）
#
#   ⚠ v2.2/v2.3 用的是 6.5mm 深度（凭空假设模块不悬出板边），
#     直接导致 3V3（J1 x=2.27 → J4 x=27.40, y 1.9~5.6）被假净空拦住布不通。
ANT_X0, ANT_X1 = DK_LEFT + 3.75, DK_LEFT + 21.75   # 4.75 .. 22.75（官方灰矩形 x）
ANT_ABOVE_TOP = 6.27                  # 模块天线伸出 DevKit 板顶边 6.27mm（悬空）
ANT_IN_BOARD = 0.52                    # 天线区搭进 DevKit 板内的深度（官方 0.52mm）
# 载板规则区：天线区的垂直投影带
ANT_KO_X0, ANT_KO_X1 = ANT_X0 - 0.2, ANT_X1 + 0.2   # 4.55 .. 22.95
ANT_KO_Y0, ANT_KO_Y1 = -1.0, ANT_IN_BOARD + 0.28   # -1.0 .. 0.80
# ★ 铺铜缺口必须比规则区更大（各外 0.15~0.20mm），否则铜箔会压在禁铜带里
ANT_CU_X0 = ANT_KO_X0 - 0.15         # 4.40
ANT_CU_X1 = ANT_KO_X1 + 0.15         # 23.10
ANT_CU_Y1 = ANT_KO_Y1 + 0.20         # 1.00

# ---- 右侧扩展区（DevKit 右侧完全露出的 26.4..44.0mm 区域）----
# ★ v2.2 布局定稿（依据 layout_audit2.py 穷举 + measure_silk_width.py 实测 + check_silk.py 复核）：
#   1.0mm 字高实测 char≈0.9mm、bbox 高 1.70mm；右侧净宽 17.6mm
#   ① J2 焊盘 x 27.1..31.24（左侧留 0.7mm 离 DevKit 板边 26.4）
#   ② 针序表放 J2 右侧，**8 行与 J2 焊盘行一一对齐**（行距同为 2.54mm）
#      条目 "<针号>:<网名>" 最宽 6 字符 = 5.68mm
#      → 双栏 31.6..37.28 / 37.6..43.28 ✓ 右边距 0.72mm
#   ③ 「板针→屏针」的奇偶换算规则在表下一行统一给出（比重复 16 次更易读）
#   ④ J4/J5 功能标签竖排（1.0mm 字高横排时 2.54mm 针距会互压）
#   ⑤ 说明文字移到板底全宽区（x 26.8..43.6 ⇒ 每行 ≤ 17 字符）
MHOLES = [(27.9, 2.8), (41.0, 2.8), (27.9, 52.4), (41.0, 52.4)]   # M2.5 (Ø3.2)
J2_XL, J2_XR = 27.9, 30.44           # HUB75 2x8 两列（排距 2.54）
J2_Y0 = 19.0                         # 第 1 行 y
TBL_XL = 31.25                       # 对照表左栏 x（J2 左列 = 奇数脚）
TBL_XR = 37.25                       # 对照表右栏 x（J2 右列 = 偶数脚）
TBL_HDR_Y = 17.0                     # 表头 y
TBL_NOTE_Y = 39.0                    # 表下换算规则说明 y
J4_Y = 5.6                           # I2C 1x4（横向）
J4_X0 = 27.4
J4_LAB_DY = 2.7                      # J4 焊盘中心 → 竖排标签中心
J5_Y = 14.6                          # UART 1x3（横向）
J5_X0 = 27.4
J5_LAB_DY = -2.7                     # J5 焊盘中心 → 竖排标签中心（放在上方）
J45_TITLE_X = 38.5                   # J4/J5 接口名 x
INFO_X = 35.2                        # 说明文字区中心 x（26.8..43.6）
INFO_Y0 = 41.4                       # 说明文字首行 y
INFO_DY = 2.0                        # 说明文字行距

OUT = r'F:/AI数据/hub75-pixel-clock/hardware/pcb/hub75-adapter.kicad_pcb'

board = pcbnew.NewBoard('hub75-adapter')

# ================= 网络 =================
NETS = ['GND', '3V3', 'R1', 'G1', 'B1', 'R2', 'G2', 'B2', 'E',
        'A', 'B', 'C', 'D', 'CLK', 'LAT', 'OE', 'SDA', 'SCL', 'UTX', 'URX']
nets = {}
for n in NETS:
    ni = NETINFO_ITEM(board, n)
    board.Add(ni)
    nets[n] = ni


# ================= 封装工具 =================
def add_tht_footprint(name, ref, pads, rect=False, square_pins=()):
    """pads: [(num, x, y)]；rect=True 时全部焊盘为方形；square_pins 指定额外方形脚号"""
    fp = FOOTPRINT(board)
    fp.SetFPID(LIB_ID('hub75ad', name))
    fp.SetReference(ref)
    fp.SetValue(name)
    fp.SetPosition(VECTOR2I(0, 0))
    ls = pcbnew.LSET()
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):
        ls.AddLayer(lay)
    for num, x, y in pads:
        p = PAD(fp)
        p.SetNumber(str(num))
        if rect or num in square_pins:
            p.SetShape(pcbnew.PAD_SHAPE_RECT)
        else:
            p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(VECTOR2I(mm(PAD_D), mm(PAD_D)))
        p.SetDrillSize(VECTOR2I(mm(DRILL), mm(DRILL)))
        p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetLayerSet(ls)
        p.SetPosition(VECTOR2I(mm(x), mm(y)))
        fp.Add(p)
    board.Add(fp)
    for fld in (fp.Reference(), fp.Value()):
        fld.SetLayer(pcbnew.F_Fab)
        fld.SetPosition(VECTOR2I(0, 0))
    return fp


def bind(fp, netmap):
    """★ 坑：fp.Pads() 返回顺序不是引脚号顺序 —— 必须按 GetNumber() 查找"""
    for p in fp.Pads():
        n = netmap.get(int(p.GetNumber()))
        if n:
            p.SetNet(nets[n])


def silk_text(text, x, y, size=0.7, align='C', thickness=0.12, rot=0):
    t = PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(VECTOR2I(mm(x), mm(y)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thickness))
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    if align == 'C':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    elif align == 'L':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    else:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


def fab_text(text, x, y, size=0.55, align='C', thickness=0.09, rot=0):
    """F.Fab 装配层文字 —— 不参与打样丝印，不会在模组下露铜压焊盘"""
    t = PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(VECTOR2I(mm(x), mm(y)))
    t.SetLayer(pcbnew.F_Fab)
    t.SetTextSize(VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thickness))
    t.SetTextAngle(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    if align == 'C':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    elif align == 'L':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    else:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


def silk_seg(x1, y1, x2, y2, w=0.15):
    s = PCB_SHAPE(board)
    s.SetShape(SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.F_SilkS)
    s.SetStart(VECTOR2I(mm(x1), mm(y1)))
    s.SetEnd(VECTOR2I(mm(x2), mm(y2)))
    s.SetWidth(mm(w))
    board.Add(s)


def silk_tri(cx, cy, r=0.45):
    """实心感 pin1 三角标记（朝上）"""
    silk_seg(cx - r, cy - r * 0.6, cx + r, cy - r * 0.6, 0.16)
    silk_seg(cx - r, cy - r * 0.6, cx, cy + r * 0.7, 0.16)
    silk_seg(cx + r, cy - r * 0.6, cx, cy + r * 0.7, 0.16)


def fab_line(x1, y1, x2, y2, w=0.1):
    s = PCB_SHAPE(board)
    s.SetShape(SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.F_Fab)
    s.SetStart(VECTOR2I(mm(x1), mm(y1)))
    s.SetEnd(VECTOR2I(mm(x2), mm(y2)))
    s.SetWidth(mm(w))
    board.Add(s)


def fab_rect(x0, y0, x1, y1):
    fab_line(x0, y0, x1, y0)
    fab_line(x1, y0, x1, y1)
    fab_line(x1, y1, x0, y1)
    fab_line(x0, y1, x0, y0)


# ================= 板框（圆角矩形，弧 mid 显式钉死） =================
def arc_mid(cx, cy, r, a1_deg, a2_deg):
    a1, a2 = math.radians(a1_deg), math.radians(a2_deg)
    d = a2 - a1
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    am = a1 + d / 2
    return (cx + r * math.cos(am), cy + r * math.sin(am))


def add_line(x1, y1, x2, y2):
    s = PCB_SHAPE(board)
    s.SetShape(SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(VECTOR2I(mm(x1), mm(y1)))
    s.SetEnd(VECTOR2I(mm(x2), mm(y2)))
    s.SetWidth(mm(OUTLINE_W))
    board.Add(s)


def add_arc(cx, cy, sx, sy, ex, ey, r):
    a = PCB_SHAPE(board)
    a.SetShape(SHAPE_T_ARC)
    a.SetLayer(pcbnew.Edge_Cuts)
    a.SetCenter(VECTOR2I(mm(cx), mm(cy)))
    a.SetStart(VECTOR2I(mm(sx), mm(sy)))
    a.SetEnd(VECTOR2I(mm(ex), mm(ey)))
    mx, my = arc_mid(cx, cy, r,
                     math.degrees(math.atan2(sy - cy, sx - cx)),
                     math.degrees(math.atan2(ey - cy, ex - cx)))
    try:
        a.SetMid(VECTOR2I(mm(mx), mm(my)))
    except Exception:
        a.SetArcGeometry(VECTOR2I(mm(sx), mm(sy)), VECTOR2I(mm(mx), mm(my)),
                         VECTOR2I(mm(ex), mm(ey)))
    a.SetWidth(mm(OUTLINE_W))
    board.Add(a)


add_line(RC, 0, W - RC, 0)
add_arc(W - RC, RC, W - RC, 0, W, RC, RC)
add_line(W, RC, W, H - RC)
add_arc(W - RC, H - RC, W, H - RC, W - RC, H, RC)
add_line(W - RC, H, RC, H)
add_arc(RC, H - RC, RC, H, 0, H - RC, RC)
add_line(0, H - RC, 0, RC)
add_arc(RC, RC, 0, RC, RC, 0, RC)

# ================= J1：DevKitC-1 左侧 22P 排母（板上焊 1~21 脚） =================
# 官方 J1 脚序（pin1 在天线端）：
#  1=3V3 2=3V3 3=RST 4=IO4 5=IO5 6=IO6 7=IO7 8=IO15 9=IO16 10=IO17 11=IO18
#  12=IO8 13=IO3 14=IO46 15=IO9 16=IO10 17=IO11 18=IO12 19=IO13 20=IO14 21=5V 22=GND
J1_NETS = {1: '3V3', 2: '3V3', 4: 'R1', 5: 'G1', 6: 'B1', 7: 'R2', 8: 'G2',
           9: 'B2', 10: 'A', 11: 'B', 12: 'C', 15: 'D', 16: 'E', 17: 'CLK',
           18: 'LAT', 19: 'OE'}

# ================= J3：DevKitC-1 右侧 22P 排母 =================
#  1=GND 2=TX(IO43) 3=RX(IO44) 4=IO1 5=IO2 6=IO42 7=IO41 8=IO40 9=IO39
#  10=IO38 11=IO37 12=IO36 13=IO35 14=IO0 15=IO45 16=IO48 17=IO47 18=IO21
#  19=IO20 20=IO19 21=GND 22=GND
J3_NETS = {1: 'GND', 2: 'UTX', 3: 'URX', 6: 'SCL', 7: 'SDA', 21: 'GND'}


def add_socket_column(name, ref, x, netmap, label_x):
    """★ v2.2：不再印逐脚序号。
    理由：① 1.0mm 字高在「板边→焊盘」仅 1.47mm 的窄缝里放不下（会压焊盘/贴板边）；
          ② ESP32-S3-DevKitC-1 模组 PCB 上本身就印有排针脚号，插上后依然可见，
             载板重复印反而是冗余且必然违规；
          ③ 防错需求由「pin1 三角标记」+「右侧 PIN1=TOP 说明」覆盖。
    """
    pads = [(i + 1, x, PIN1_Y + i * PITCH) for i in range(NPIN)]
    fp = add_tht_footprint(name, ref, pads, square_pins=(1,))
    bind(fp, netmap)
    return fp


add_socket_column('Socket_1x22_L', 'J1', J1_X, J1_NETS, 0.70)
add_socket_column('Socket_1x22_R', 'J3', J3_X, J3_NETS, 26.90)

# pin1 三角标记（J1 / J3 顶部，朝上）
silk_tri(J1_X, 0.55, 0.40)
silk_tri(J3_X, 0.55, 0.40)

# ================= J2：HUB75 2x8 排母（针序 = 旧板 J1，实测可用） =================
# ★ 针序以「旧板 J1 逐脚承载的 GPIO」为准（读自 j1_zoom.png 原理图）：
#   板针 1←GPIO5  2←GPIO4  3←GND  4←GPIO6  5←GPIO15 6←GPIO7  7←GPIO10
#   8←GPIO16  9←GPIO18 10←GPIO17 11←GPIO9 12←GPIO8 13←GPIO12 14←GPIO11
#   15←GND  16←GPIO13
#   排线两列对调后：板针 n → 屏针 n±1（奇→+1，偶→-1）
#   ⇒ GPIO12→屏14(LAT)、GPIO11→屏13(CLK)、GPIO13→屏15(OE)，与 config.h 完全一致
J2_NETS = {1: 'G1', 2: 'R1', 3: 'GND', 4: 'B1', 5: 'G2', 6: 'R2', 7: 'E',
           8: 'B2', 9: 'B', 10: 'A', 11: 'D', 12: 'C', 13: 'LAT', 14: 'CLK',
           15: 'GND', 16: 'OE'}
# 对应屏针号（屏标准序）：屏1=R1 2=G1 3=B1 4=GND 5=R2 6=G2 7=B2 8=E 9=A
# 10=B 11=C 12=D 13=CLK 14=LAT 15=OE 16=GND
J2_SCREEN = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7,
             9: 10, 10: 9, 11: 12, 12: 11, 13: 14, 14: 13, 15: 16, 16: 15}

j2_pads = []
for row in range(8):
    y = J2_Y0 + row * PITCH
    j2_pads.append((row * 2 + 1, J2_XL, y))    # 奇数脚 左列
    j2_pads.append((row * 2 + 2, J2_XR, y))    # 偶数脚 右列
fp_j2 = add_tht_footprint('Socket_2x8_HUB75', 'J2', j2_pads, square_pins=(1,))
bind(fp_j2, J2_NETS)

# ================= J2 针序对照表（双栏 × 8 行，与 J2 焊盘行对齐） =================
# ★ v2.2 关键改动：
#   ① 原单栏 "1:G1>P2   2:R1>P1" 在 0.45mm 字高下会糊 → 全部提到 1.0mm
#   ② 1.0mm 下条目必须精简到 6 字符内（"13:LAT>14" = 8.45mm 塞不进窄带）
#      → 条目 "<针号>:<网名>"（最宽 "15:GND" = 5.68mm）
#      → 「板针 → 屏针」的奇偶换算规则在表下一行统一给出
#   ③ 表格 8 行与 J2 的 8 行焊盘**行距同为 2.54mm、一一对齐** → 横向对读即映射
#   ④ 左栏 = J2 左列 = 奇数脚；右栏 = J2 右列 = 偶数脚
# ★ 全部 ASCII：中文丝印在嘉立创打样会出方块字
silk_text('ODD', TBL_XL, TBL_HDR_Y, SILK_MIN_H, 'L', SILK_MIN_T)
silk_text('EVEN', TBL_XR, TBL_HDR_Y, SILK_MIN_H, 'L', SILK_MIN_T)
for row in range(8):
    y = J2_Y0 + row * PITCH          # ★ 与 J2 焊盘行同 y
    a = row * 2 + 1                   # 奇数脚 → 左栏
    b = row * 2 + 2                   # 偶数脚 → 右栏
    silk_text('%d:%s' % (a, J2_NETS[a]), TBL_XL, y, SILK_MIN_H, 'L', SILK_MIN_T)
    silk_text('%d:%s' % (b, J2_NETS[b]), TBL_XR, y, SILK_MIN_H, 'L', SILK_MIN_T)
# 表下换算规则（1 行说清，替代在 16 个条目里重复 ">屏针号"）
# ★ 实测 "SCREEN PIN: ODD+1 EVEN-1" 宽 22.49mm 超边 → 拆成「左栏规则 + 右栏规则」
silk_text('ODD+1', TBL_XL, TBL_NOTE_Y, SILK_MIN_H, 'L', SILK_MIN_T)
silk_text('EVEN-1', TBL_XR, TBL_NOTE_Y, SILK_MIN_H, 'L', SILK_MIN_T)
# J2 pin1 三角（在 J2 焊盘上方；离焊盘开窗留足距离，避免 DRC「丝印被阻焊裁切」）
silk_tri(J2_XL, J2_Y0 - 1.55, 0.40)

# ================= J4：I2C 1x4 排针 =================
J4_NETS = {1: '3V3', 2: 'GND', 3: 'SDA', 4: 'SCL'}
J4_LABELS = ['3V3', 'GND', 'SDA', 'SCL']
j4_pads = [(i + 1, J4_X0 + i * PITCH, J4_Y) for i in range(4)]
fp_j4 = add_tht_footprint('PinHeader_1x4', 'J4', j4_pads, square_pins=(1,))
bind(fp_j4, J4_NETS)
# ★ 1.0mm 字高横排时相邻标签会互压（2.54mm 针距 vs 3.3mm 宽的 "GND"）
#   → 标签竖排（旋转 90°），每个占 1.70mm 宽，针距 2.54mm ✓
for i, lab in enumerate(J4_LABELS):
    silk_text(lab, J4_X0 + i * PITCH, J4_Y + J4_LAB_DY, SILK_MIN_H, 'C', SILK_MIN_T, 90)
silk_text('I2C', J45_TITLE_X, J4_Y, SILK_MIN_H, 'C', SILK_MIN_T)

# ================= J5：UART 1x3 排针（调试串口） =================
J5_NETS = {1: 'UTX', 2: 'URX', 3: 'GND'}
J5_LABELS = ['TX', 'RX', 'GND']
j5_pads = [(i + 1, J5_X0 + i * PITCH, J5_Y) for i in range(3)]
fp_j5 = add_tht_footprint('PinHeader_1x3', 'J5', j5_pads, square_pins=(1,))
bind(fp_j5, J5_NETS)
for i, lab in enumerate(J5_LABELS):
    silk_text(lab, J5_X0 + i * PITCH, J5_Y + J5_LAB_DY, SILK_MIN_H, 'C', SILK_MIN_T, 90)
silk_text('UART', J45_TITLE_X, J5_Y, SILK_MIN_H, 'C', SILK_MIN_T)

# ================= 安装孔 M2.5 =================
for i, (hx, hy) in enumerate(MHOLES):
    fp = FOOTPRINT(board)
    fp.SetFPID(LIB_ID('hub75ad', 'MountingHole_3.2mm'))
    fp.SetReference('H%d' % (i + 1))
    fp.SetValue('MountingHole_3.2mm')
    fp.SetPosition(VECTOR2I(mm(hx), mm(hy)))
    ls = pcbnew.LSET()
    for lay in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):
        ls.AddLayer(lay)
    p = PAD(fp)
    p.SetNumber('1')
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(VECTOR2I(mm(3.2), mm(3.2)))
    p.SetDrillSize(VECTOR2I(mm(3.2), mm(3.2)))
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetLayerSet(ls)
    p.SetPosition(VECTOR2I(mm(hx), mm(hy)))
    fp.Add(p)
    board.Add(fp)
    for fld in (fp.Reference(), fp.Value()):
        fld.SetLayer(pcbnew.F_Fab)
        fld.SetPosition(VECTOR2I(0, 0))

# ================= F.Fab：DevKitC-1 装配轮廓（裁到载板范围内） =================
# DevKitC-1 全长 62.74mm，但载板只有 54.5mm，底部 8.24mm 是 USB 区（不覆盖）
fab_rect(DK_LEFT, 0.0, DK_RIGHT, H)
# ★ 说明文字放 F.Fab 装配层：它横跨整个 DevKit 覆盖区（x 1.0~26.4），
#   印在 F.SilkS 上会被模组盖住、且会压住 J1/J3 的焊盘 → 一律移到 F.Fab
fab_text('DEVKITC-1 OUTLINE 25.4x62.74 (USB BELOW BOARD)',
         (DK_LEFT + DK_RIGHT) / 2, 26.0, 0.55, 'C', 0.09)

# ================= 右侧说明区丝印（全部 ASCII，避免打样方块字） =================
# ★ v2.2：字符高度全部提到 1.0mm（嘉立创常规工艺下限）
#   实测 1.0mm 字高：char≈0.9mm、bbox 高 1.70mm
#   板底全宽区 x 26.8..43.6 = 16.8mm ⇒ 每行 ≤ 17 字符（实测上限）
#   行内容按实测宽度裁剪（见 measure_silk_width.py）
silk_text('HUB75 ADAPTER v2.4', INFO_X, INFO_Y0, SILK_MIN_H, 'C', SILK_MIN_T)
silk_text('ESP32-S3-DEVKITC', INFO_X, INFO_Y0 + INFO_DY, SILK_MIN_H, 'C', SILK_MIN_T)
silk_text('FLIP 2 COLUMNS', INFO_X, INFO_Y0 + 2 * INFO_DY, SILK_MIN_H, 'C', SILK_MIN_T)
silk_text('SAME AS OLD PCB', INFO_X, INFO_Y0 + 3 * INFO_DY, SILK_MIN_H, 'C', SILK_MIN_T)
silk_text('PIN1=TOP ROW 22.86', INFO_X, INFO_Y0 + 4 * INFO_DY, SILK_MIN_H, 'C', SILK_MIN_T)

# ================= 天线净空规则区（禁走线 + 禁铺铜 + 禁过孔）=================
# ★ v2.3：用 KiCad 原生「规则区」表达天线净空，而不是只靠铺铜凹口。
#   规则区会被 KiCad 导出成 DSN 的 (keepout "" (polygon ...))，Freerouting 认这个语法
#   ⇒ 走线/过孔自动被挡在天线区之外（v2.2 只做铺铜凹口，走线照样能穿进去）
#   注：板面区 = 官方禁铜区 x[4.75,22.75] y[0,6.5]；规则区再外扩 0.2mm 留裕量
ant_ko = ZONE(board)
ant_ko.SetIsRuleArea(True)
ant_ko.SetDoNotAllowTracks(True)
ant_ko.SetDoNotAllowVias(True)
ant_ko.SetDoNotAllowPads(True)
ant_ko.SetDoNotAllowZoneFills(True)
ant_ko.SetDoNotAllowFootprints(True)
# ★ 注意：ZONE.SetLayer() 是「覆盖」语义，连续调两次只会剩最后一层
#   ⇒ 必须用 SetLayerSet() 一次性设置 F.Cu + B.Cu
_ls = pcbnew.LSET()
_ls.addLayer(pcbnew.F_Cu)
_ls.addLayer(pcbnew.B_Cu)
ant_ko.SetLayerSet(_ls)
aks = SHAPE_POLY_SET()
aks.NewOutline()
for (x, y) in [(ANT_KO_X0, ANT_KO_Y0), (ANT_KO_X1, ANT_KO_Y0),
               (ANT_KO_X1, ANT_KO_Y1), (ANT_KO_X0, ANT_KO_Y1)]:
    aks.Append(mm(x), mm(y))
ant_ko.SetOutline(aks)
board.Add(ant_ko)
print('antenna rule area added: x[%.2f,%.2f] y[%.2f,%.2f]'
      % (ANT_KO_X0, ANT_KO_X1, ANT_KO_Y0, ANT_KO_Y1))

# ================= 底层 GND 铺铜（天线区留空） =================
z = ZONE(board)
z.SetLayer(pcbnew.B_Cu)
z.SetNet(nets['GND'])
z.SetLocalClearance(mm(0.25))
z.SetMinThickness(mm(0.25))
# ★ v2.3：GND 焊盘改为「实心连接」(FULL) —— 这是修 DRC 的关键
#   病根：J3-1 在 (25.13, 1.88)，而铺铜上边界在 y=0.5，
#         热焊盘间隙 0.5mm ⇒ 顶部那根花焊盘引线被板边切没，只剩 1 条
#         ⇒ DRC 报「热焊盘连接不完整 + 焊盘未连上铺铜」
#   实心连接后 GND 焊盘直接与 B.Cu 铜皮融合，不依赖花焊盘引线
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
z.SetThermalReliefGap(mm(0.3))
z.SetThermalReliefSpokeWidth(mm(0.5))
ps = SHAPE_POLY_SET()
ps.NewOutline()
# 凹多边形：顶部中间挖出天线净空带。
# ★ 缺口（不铺铜的区域）必须比规则区**更大**，否则铜箔会压在禁铜带里：
#   规则区 x[4.55, 22.95] y[-1.0, 0.80]
#   缺口   x[4.40, 23.10] y[-1.0, 1.00]   ← 各向外 0.15mm
outline = [(0.5, 0.5), (ANT_CU_X0, 0.5), (ANT_CU_X0, ANT_CU_Y1), (ANT_CU_X1, ANT_CU_Y1),
           (ANT_CU_X1, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5),
           (0.5, H - 0.5)]
for (x, y) in outline:
    ps.Append(mm(x), mm(y))
z.SetOutline(ps)
board.Add(z)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())

# ================= 保存 =================
io = pcbnew.PCB_IO_KICAD_SEXPR()
io.SaveBoard(OUT, board)
print('saved:', OUT)
print('footprints:', len(board.GetFootprints()))
pads = sum(len(fp.Pads()) for fp in board.GetFootprints())
print('pads:', pads)
print('board: %.1f x %.1f mm' % (W, H))
print('J1 x=%.4f  J3 x=%.4f  row gap=%.4f  pin1 y=%.4f  pin21 y=%.4f'
      % (J1_X, J3_X, ROW_GAP, PIN1_Y, PIN1_Y + (NPIN - 1) * PITCH))
print('antenna keepout (rule area): x[%.2f, %.2f]  y[%.2f, %.2f]'
      % (ANT_KO_X0, ANT_KO_X1, ANT_KO_Y0, ANT_KO_Y1))
print('  (官方灰矩形 x[%.2f,%.2f] y[-%.2f,%.2f]，模块天线悬出板顶边 %.2fmm)'
      % (ANT_X0, ANT_X1, ANT_ABOVE_TOP, ANT_IN_BOARD, ANT_ABOVE_TOP))
