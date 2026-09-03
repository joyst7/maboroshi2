# -*- coding: utf-8 -*-
"""
幻鉱 -MABOROSHI-  スプライト生成スクリプト

  このファイルを実行すると maboroshi.pyxres が出力される。
  ゲーム本体はそれを読むだけなので、出力後は Pyxel Editor で自由に描き直してよい。

    pyxel edit maboroshi.pyxres

  約束ごと:
    色0 = 透明（描画時に抜ける）
    色1 = 輪郭線
"""
import math
import random

import pyxel

TRANSPARENT = 0
OUTLINE = 1

# ==============================================================================
#  スプライトの置き場所（Pyxel Editorで探すときの目印）
# ==============================================================================
#   坑夫      (0,0)-(31,15)    16x16 x2   立ち / 振り
#   鉱石      (0,16)-(79,31)   16x16 x5   銅 鉄 銀 金 宝石
#   幻の鉱床  (0,32)-(47,55)   24x24 x2   明 / 暗
#   タイル    (0,56)-(63,63)    8x8  x8   床4種 / 瓦礫3種 / 壁1種
#   ハシゴ    (0,64)-(15,87)   16x24 x1
# ==============================================================================

# --- 坑夫 ---------------------------------------------------------------------
#  A=黄(ヘルメット) F=肌 7=白ヒゲ 5=服 4=ベルト・靴 C=ランプの光
MINER_STAND = [
    "................",
    "....111111......",
    "...1AAAAAA1.....",
    "..1AAAAAAAA1....",
    "..1AAAAAAAA1.C..",
    "..11111111111CC.",
    "...1FF11FF1..C..",
    "...1FFFFFF1.....",
    "..17777777771...",
    "..17777777771...",
    "..1177777711....",
    "...15555551.....",
    "...15555551.....",
    "...14444441.....",
    "...144..441.....",
    "...111..111.....",
]
MINER_SWING = [
    "................",
    "................",
    "....111111......",
    "...1AAAAAA1.....",
    "..1AAAAAAAA1.C..",
    "..1AAAAAAAA1CC..",
    "..11111111111...",
    "...1FF11FF1.....",
    "...1FFFFFF1.....",
    "..17777777771...",
    "..17777777771...",
    "..1177777711....",
    "...15555551.....",
    "...14444441.....",
    "..1444..4441....",
    "..111....111....",
]

CHAR_COLS = {
    ".": None, "1": 1, "A": 10, "F": 15, "7": 7,
    "5": 5, "4": 4, "C": 10, "6": 6, "9": 9, "2": 2,
}

# --- ハシゴ -------------------------------------------------------------------
LADDER = [
    "..1111....1111..",
    "..1449....94411.",
    "..1449....9441..",
    "..1449....9441..",
    ".1111111111111..",
    ".199999999991...",
    ".1111111111111..",
    "..1449....9441..",
    "..1449....9441..",
    "..1449....9441..",
    ".1111111111111..",
    ".199999999991...",
    ".1111111111111..",
    "..1449....9441..",
    "..1449....9441..",
    "..1449....9441..",
    ".1111111111111..",
    ".199999999991...",
    ".1111111111111..",
    "..1449....9441..",
    "..1449....9441..",
    "..1449....9441..",
    "..1111....1111..",
    "................",
]


def paint(img, ox, oy, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            c = CHAR_COLS.get(ch)
            if c is not None:
                img.pset(ox + x, oy + y, c)


# ==============================================================================
#  鉱石（岩の塊を手続きで生成する。輪郭・面・影・きらめきの4層）
# ==============================================================================
def paint_ore(img, ox, oy, size, base, dark, shine, seed, facet=True):
    """16x16の枠のなかに、直径sizeの岩を描く。"""
    rng = random.Random(seed)
    cx = cy = 8.0
    r = size / 2.0

    # 輪郭がガタつくよう、角度ごとに半径を少し揺らす
    wob = [rng.uniform(-0.8, 0.8) for _ in range(12)]

    def radius_at(a):
        i = (a / math.tau * 12) % 12
        i0, i1 = int(i), (int(i) + 1) % 12
        t = i - int(i)
        return r + wob[i0] * (1 - t) + wob[i1] * t

    inside = []
    for y in range(16):
        for x in range(16):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(dx, dy)
            if d <= radius_at(math.atan2(dy, dx) % math.tau):
                inside.append((x, y, d))

    for x, y, d in inside:
        img.pset(ox + x, oy + y, base)

    # 輪郭
    for x, y, d in inside:
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not any(p[0] == nx and p[1] == ny for p in inside):
                img.pset(ox + x, oy + y, OUTLINE)
                break

    # 下側に影、上左に面の明るさ
    for x, y, d in inside:
        if img.pget(ox + x, oy + y) == OUTLINE:
            continue
        if (y - cy) + (x - cx) * 0.4 > r * 0.35:
            img.pset(ox + x, oy + y, dark)

    if facet:
        # 結晶のきらめきを数点だけ置く（ファミコン風に点で表現）
        for _ in range(max(2, size // 5)):
            a, dd = rng.uniform(0, math.tau), rng.uniform(0, r * 0.55)
            px, py = int(cx + math.cos(a) * dd), int(cy + math.sin(a) * dd)
            if 0 <= px < 16 and 0 <= py < 16 and img.pget(ox + px, oy + py) not in (0, OUTLINE):
                img.pset(ox + px, oy + py, shine)

    # 光沢のハイライト（左上に2px）
    hx, hy = int(cx - r * 0.42), int(cy - r * 0.45)
    for dx in range(2):
        if 0 <= hx + dx < 16 and 0 <= hy < 16:
            if img.pget(ox + hx + dx, oy + hy) not in (0, OUTLINE):
                img.pset(ox + hx + dx, oy + hy, 7)


def paint_phantom(img, ox, oy, base, dark, edge, seed):
    """24x24。角ばった結晶にして、普通の丸い鉱石と一目で区別できるようにする。"""
    rng = random.Random(seed)
    cx = cy = 12.0
    pts = []
    n = 7
    for i in range(n):
        a = math.tau * i / n - math.pi / 2
        rr = 10.5 + rng.uniform(-1.2, 1.2)
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))

    def inside_poly(px, py):
        c = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi:
                c = not c
            j = i
        return c

    cells = [(x, y) for y in range(24) for x in range(24) if inside_poly(x + 0.5, y + 0.5)]
    s = set((x, y) for x, y in cells)
    for x, y in cells:
        img.pset(ox + x, oy + y, base)
    for x, y in cells:
        if not all((nx, ny) in s for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1))):
            img.pset(ox + x, oy + y, edge)
    # 中心から放射する面の分割線で結晶感を出す
    for i in range(0, n, 2):
        a = math.tau * i / n - math.pi / 2 + math.pi / n
        for t in range(5, 10):
            px, py = int(cx + math.cos(a) * t), int(cy + math.sin(a) * t)
            if (px, py) in s:
                img.pset(ox + px, oy + py, dark)
    for x, y in cells:
        if (y - cy) + (x - cx) * 0.3 > 6 and img.pget(ox + x, oy + y) == base:
            img.pset(ox + x, oy + y, dark)
    img.pset(ox + 8, oy + 7, 7)
    img.pset(ox + 9, oy + 7, 7)


# ==============================================================================
#  タイル（8x8）
# ==============================================================================
def paint_floor_tile(img, ox, oy, seed):
    """洞窟の床。色4を地、色5を粒に使う。階層ごとにpalで置き換える前提。"""
    rng = random.Random(seed)
    for y in range(8):
        for x in range(8):
            img.pset(ox + x, oy + y, 4)
    for _ in range(rng.randint(2, 4)):
        img.pset(ox + rng.randint(0, 7), oy + rng.randint(0, 7), 0)
    if rng.random() < 0.5:
        img.pset(ox + rng.randint(0, 7), oy + rng.randint(0, 7), 9)


def paint_rubble(img, ox, oy, seed):
    """床に転がる瓦礫。輪郭付きの小さな塊。"""
    rng = random.Random(seed)
    w, h = rng.randint(5, 8), rng.randint(4, 6)
    x0, y0 = rng.randint(0, 8 - w), rng.randint(0, 8 - h)
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            img.pset(ox + x, oy + y, 13)
    for x in range(x0, x0 + w):
        img.pset(ox + x, oy + y0 + h - 1, 1)
    for y in range(y0, y0 + h):
        img.pset(ox + x0, oy + y, 1)
    img.pset(ox + x0 + 1, oy + y0, 7)


def paint_wall_tile(img, ox, oy, seed):
    """盤面のふちに置く岩壁。"""
    rng = random.Random(seed)
    for y in range(8):
        for x in range(8):
            img.pset(ox + x, oy + y, 1)
    for x in range(8):
        img.pset(ox + x, oy + 0, 5)
    for _ in range(rng.randint(3, 5)):
        img.pset(ox + rng.randint(0, 7), oy + rng.randint(2, 7), 0)


# ==============================================================================
def build():
    pyxel.init(64, 64, headless=True)
    img = pyxel.images[0]
    img.cls(TRANSPARENT)

    paint(img, 0, 0, MINER_STAND)
    paint(img, 16, 0, MINER_SWING)

    #            x    直径 地  影  輝き  種
    ores = [
        (0, 12, 9, 4, 10, 11),      # 銅
        (16, 14, 13, 5, 6, 22),     # 鉄
        (32, 15, 7, 13, 7, 33),     # 銀
        (48, 16, 10, 9, 7, 44),     # 金
        (64, 16, 11, 3, 7, 55),     # 宝石
    ]
    for x, size, base, dark, shine, seed in ores:
        paint_ore(img, x, 16, size, base, dark, shine, seed)

    paint_phantom(img, 0, 32, 8, 2, 1, 77)
    paint_phantom(img, 24, 32, 14, 8, 1, 77)

    for i in range(4):
        paint_floor_tile(img, i * 8, 56, 100 + i)
    for i in range(3):
        paint_rubble(img, 32 + i * 8, 56, 200 + i)
    paint_wall_tile(img, 56, 56, 300)

    paint(img, 0, 64, LADDER)

    pyxel.save("maboroshi.pyxres")
    print("maboroshi.pyxres を書き出した")


if __name__ == "__main__":
    build()
