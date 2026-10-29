#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
make_mario_demo.py — 用 Mari0 开源素材构建 64x64「超级马里奥」时钟背景演示动画

素材来源：github.com/Stabyourself/mari0 （graphics/SMB/player/marioanimations.png 等）
授权：素材 BY-NC-SA 3.0（任天堂 IP 衍生）——仅限个人把玩，不得商用/公开发布
布局依据：mari0 main.lua 官方 quad 定义
  - 小马里奥 20x20 网格，第 0 行=1P：x=0 站立 / 20,40,60 跑步 / 100 跳跃
  - 板栗仔 16x16 网格，第 0 行=左走两帧

输出：mario_demo.gif（8 帧循环）+ 直接可推的帧数据
"""
import math
import os
import sys

from PIL import Image, ImageDraw

W = H = 64
GROUND_Y = 48          # 地面顶边
SKY = (92, 148, 252)   # SMB 经典天蓝 #5C94FC
GROUND = (228, 156, 49)  # SMB 地面橙
GROUND_DK = (0, 0, 0)
HILL = (0, 168, 0)
WHITE = (255, 255, 255)

TOOLS = os.path.dirname(os.path.abspath(__file__))


def recolor_classic(spr, cell_h=20):
    """Mari0 素材包默认是橄榄帽（玩家配色变体），重着色成经典马里奥：
    帽区(上 45%) -> 红，身区(中 40%) -> 蓝，鞋区(下 15%) -> 棕"""
    out = spr.copy()
    px = out.load()
    RED = (206, 32, 32)
    BLUE = (48, 88, 216)
    BROWN = (152, 84, 32)
    hat_end = int(cell_h * 0.45)
    shoe_start = int(cell_h * 0.85)
    for y in range(cell_h):
        for x in range(spr.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if (r, g, b) == (134, 112, 0):  # 橄榄色 -> 按区域映射
                if y < hat_end:
                    px[x, y] = RED + (a,)
                elif y >= shoe_start:
                    px[x, y] = BROWN + (a,)
                else:
                    px[x, y] = BLUE + (a,)
    return out


def load_mario_frames():
    """从 marioanimations.png 取 1P 马里奥：站立 + 跑步 3 帧（重着色为经典配色）"""
    im = Image.open(os.path.join(TOOLS, "mari0_marioanimations.png")).convert("RGBA")
    quads = {
        "idle": (0, 0), "run1": (20, 0), "run2": (40, 0),
        "run3": (60, 0), "jump": (100, 0),
    }
    out = {}
    for k, (x, y) in quads.items():
        out[k] = recolor_classic(im.crop((x, y, x + 20, y + 20)))
    return out


def load_goomba_frames():
    """goomba.png 32x64 = 2 列 x 4 行 16x16，第 0 行左走"""
    im = Image.open(os.path.join(TOOLS, "mari0_goomba.png")).convert("RGBA")
    return [im.crop((0, 0, 16, 16)), im.crop((16, 0, 16, 16))]


def draw_clouds(d):
    d.ellipse([6, 8, 22, 18], fill=WHITE)
    d.ellipse([16, 4, 32, 18], fill=WHITE)
    d.rectangle([6, 13, 32, 18], fill=WHITE)
    d.ellipse([44, 16, 56, 24], fill=WHITE)
    d.ellipse([52, 12, 64, 24], fill=WHITE)


def draw_hills(d):
    # 远山（绿色三角）
    d.polygon([(2, GROUND_Y), (14, GROUND_Y - 16), (26, GROUND_Y)], fill=HILL)
    d.polygon([(38, GROUND_Y), (50, GROUND_Y - 12), (62, GROUND_Y)], fill=HILL)


def draw_ground(d):
    d.rectangle([0, GROUND_Y, W - 1, H - 1], fill=GROUND)
    # 经典 SMB 地面斑点：每个 16x16 瓦片 3 个黑点
    for ty in range(GROUND_Y, H, 16):
        for tx in range(0, W, 16):
            d.rectangle([tx + 2, ty + 2, tx + 5, ty + 5], fill=GROUND_DK)
            d.rectangle([tx + 10, ty + 8, tx + 13, ty + 11], fill=GROUND_DK)


def build(fps=8):
    mario = load_mario_frames()
    goombas = load_goomba_frames()
    frames = []
    n = 8
    run_cycle = [mario["run1"], mario["run2"], mario["run3"]]
    for i in range(n):
        im = Image.new("RGB", (W, H), SKY)
        d = ImageDraw.Draw(im)
        draw_clouds(d)
        draw_hills(d)
        draw_ground(d)

        # 马里奥：每帧左移 8px，跑出左边界后从右边回来
        mx = W - 20 - i * 8
        if mx < -20:
            mx += W + 20
        my = GROUND_Y - 20
        im.paste(run_cycle[i % 3], (mx, my), run_cycle[i % 3])

        # 板栗仔：反向走，两帧交替
        gx = -16 + ((i * 5) % (W + 32))
        gy = GROUND_Y - 16
        gf = goombas[i % 2]
        im.paste(gf, (gx, gy), gf)

        frames.append(im)
    return frames


def main():
    frames = build()
    out_gif = os.path.join(TOOLS, "mario_demo.gif")
    frames[0].save(out_gif, save_all=True, append_images=frames[1:],
                   duration=125, loop=0, disposal=2)
    print("[GIF] %s  %d frames  %.1f KB" % (
        out_gif, len(frames), os.path.getsize(out_gif) / 1024))
    # 统计验证：地面/天空/角色像素占比
    f0 = frames[0]
    px = f0.load()
    sky_n = sum(1 for y in range(H) for x in range(W) if px[x, y] == SKY)
    gnd_n = sum(1 for y in range(GROUND_Y, H) for x in range(W))
    print("[STATS] frame0: sky=%d ground=%d total=%d" % (sky_n, gnd_n, W * H))


if __name__ == "__main__":
    main()
