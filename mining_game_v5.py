# -*- coding: utf-8 -*-
"""
================================================================================
  幻鉱 -MABOROSHI-   採掘クリッカー  (Pyxel)
================================================================================
  操作:
    矢印キー ... 移動
    Z ......... 採掘（押しっぱなしで自動連打。手動連打はそれより速く掘れる）
    X ......... ハシゴを降りる
    S ......... ショップ
    C ......... 怪しい薬を飲む
    M ......... BGM ON/OFF
    R ......... リスタート（クリア後）
    ESC ....... 終了

  遊び方:
    鉱石を掘って資源とEXPを稼ぎ、ショップでピッケルと能力を強化する。
    各階層には「幻の鉱床」が現れる。よく見かけるが、誰も壊したことがない。
    その階層の幻を砕くと下へのハシゴが開く。B5Fの幻を砕けばクリア。
================================================================================
"""

import math
import os
import random

import pyxel

# ==============================================================================
#  画面レイアウト
#    盤面(FIELD)とUI帯を完全に分離する。鉱石や数字がテロップに重ならないように、
#    盤面の描画はクリップ領域で切り取る。
# ==============================================================================
SCREEN_W = 256
SCREEN_H = 256
FPS = 30

UI_TOP_H = 30                  # 上部の情報帯
FIELD_TOP = UI_TOP_H
FIELD_BOTTOM = 194             # ここから下は下部コマンド帯
UI_BOTTOM_Y = FIELD_BOTTOM

# 下部コマンド帯の各行のY座標
ROW_PH1 = 198                  # 幻の鉱床: 名前とゲージ
ROW_PH2 = 212                  # 幻の鉱床: 残り時間と必要時間
ROW_INFO = 226                 # メッセージ / コンボ / バフ
ROW_HINT = 241                 # 操作ヒント

# ==============================================================================
#  ゲーム定数
# ==============================================================================
MAX_ORE_ON_SCREEN = 7
ORE_SPAWN_INTERVAL = 22
ORE_LIFETIME_MIN = 25 * FPS
ORE_LIFETIME_MAX = 50 * FPS

MINE_REACH = 9
COMBO_TIMEOUT = 20
COMBO_MAX = 100

PHANTOM_LIFETIME_MIN = 32 * FPS
PHANTOM_LIFETIME_MAX = 78 * FPS
PHANTOM_COOLDOWN = 18 * FPS
PHANTOM_SPAWN_CHANCE = 0.4
PHANTOM_WARN_TIME = 10 * FPS

# --- 怪しい薬 -----------------------------------------------------------------
#   旧「強化薬」。5倍20秒は強すぎた。最終ピッケルより安いのに、装備なしで
#   最終ボスを殴り倒せてしまう。バイキルトが2倍であることを思えば、5倍も4倍も狂っている。
#   そこで 1.5〜3.0倍の4段階に刻み、飲むまで効き目が分からないようにする。
#   計算ずくのブースト運用ができなくなり、ボス前の一杯が博打になる。
#   運は「良い段が出る確率」と「効き目の長さ」の両方に効く。
POTION_TIERS = (
    # (倍率, 基本の重み, 運1あたりの重みの増減)
    (1.5, 46, -2.0),
    (2.0, 32, 0.0),
    (2.5, 17, 1.4),
    (3.0, 5, 1.2),
)
POTION_SEC_MIN = 10
POTION_SEC_MAX = 22
POTION_LUCK_SEC = 0.05     # 運が高いほど長い方に寄る
POTION_PER_FLOOR = 3       # 1フロアで買える上限。まとめ買いは残すが青天井にはしない

# --- 画面の揺れ ---------------------------------------------------------------
#   毎フレーム乱数で座標をずらすと、掘り続けている間ずっと細かいノイズが乗って
#   画面酔いする。当たった向きへ一度だけ弾いて、あとは振幅を減らしながら往復させる。
#   通常ヒットと会心では揺らさない（頻度が高すぎて揺れっぱなしになるため）。
#   手応えは粒子・効果音・ポップアップ側で既に出している。
SHAKE_BREAK = 1.6          # 鉱石を砕いた
SHAKE_PHANTOM = 4.0        # 幻の鉱床を砕いた
SHAKE_HIT = 2.4            # 邪魔者に弾かれた
SHAKE_DECAY = 0.80         # 1フレームごとの減衰率
SHAKE_SPEED = 1.7          # 往復の速さ
SHAKE_MIN = 0.25           # これを下回ったら止める

# --- 邪魔者（坑道のコウモリ）---------------------------------------------------
#   鉱石も金も奪わない。仕事は「プレイヤーを1秒どかすこと」だけ。
#   どかされると COMBO_TIMEOUT の 0.67秒を割ってコンボが切れ、
#   火力が最大2倍から1倍に落ちる。HPよりもそちらが本当の罰。
#   加速を鈍くしてあるので、引きつけて横に避ければ曲がりきれずに通り過ぎる。
#   避けたら報われること。永久に追尾されると「避ける」が「延命」にしかならず、
#   ずっと逃げ続けるだけの作業になる。だから狙うのは一度きりの突進に限る。
#   突進が終われば舵を切らず、そのまま飛び抜けて画面の外へ消える。
#   追尾は「2秒で必ず去る」を守ったまま、その2秒の精度だけを段階で持つ。
#   緩すぎると、幻の鉱床が大きいせいで掘り判定を保ったまま数pxずれるだけで
#   避けられてしまい、避けることにコストが無くなる（＝ネコを買う価値も消える）。
#   狙いは「避けるなら掘り判定の外まで出て、コンボが切れる前に戻る」を強制すること。
#
#   ここの手触りは計算では出せなかった（シミュレーションを2通り書いて2回とも外した）ので、
#   実機で 1〜5 キーで切り替えて選んだ。結果、いちばん強い「鬼」を採用。
#   上手い人には「脳死で掘るな、1フロア3回被弾は駄目」という緩い条件にしかならず、
#   矢印キーに不慣れな人には本物の脅威になる。同じ数字が層ごとに別の意味を持つ。
#   PEST_PRESETS は深層(B6+)で段を上げるための梯子としても使える。
TUNING = False
PEST_PRESETS = (
    #  名前        当たり判定  舵が切れる距離  加速   速度倍率
    ("そのまま",        9,        20,        0.28,   1.00),
    ("少し強い",       11,        15,        0.32,   1.05),
    ("強い",           12,        11,        0.38,   1.12),
    ("かなり強い",      14,         8,        0.45,   1.20),
    ("鬼",             16,         6,        0.55,   1.30),
)
PEST_LEVEL = 4
PEST_CHASE_TIME = 2 * FPS  # これを過ぎたら狙うのをやめて飛び去る


def pest_tuning():
    """(名前, 当たり判定, 舵が切れる距離, 加速, 速度倍率)"""
    return PEST_PRESETS[PEST_LEVEL]
PEST_MAX_LIFE = 9 * FPS    # 何があっても消える保険
PEST_KNOCKBACK = 3.2
PEST_LEAVE_TIME = 3 * FPS  # 当てたあと去るまで

#   運は「出現間隔」と「予告の長さ」に効く。どちらも数値はUIに出さない。
PEST_LUCK_INTERVAL = 0.05  # 運1につき間隔 +5%
PEST_LUCK_WARN = 0.7       # 運1につき予告 +0.7フレーム

PLAYER_MAX_HP = 3
PLAYER_INVULN = 1 * FPS

# --- ほりほりネコ -------------------------------------------------------------
#   掘りは手伝わない。邪魔者を追い払い、たまに落とし物を見つけてくる。
#   ……が、本当の役目はそこではなく、坑道にネコがいるという、それだけのことにある。
#   守りにはクールタイムがあるので、群れには通用しない。万能にはしない。
#   値段は「金のピッケル(45000)を買うのが一段遅れる」ことを狙って置いてある。
#   速攻ビルドには割に合わず、運ビルドには落とし物ですぐ元が取れる。
#   つまりネコを買うかどうか自体が、どっちを目指すかの表明になる。
CAT_PRICE = 30000
CAT_SPEED = 1.9
CAT_FOLLOW_DIST = 17       # これより近ければ座って待つ
CAT_GUARD_R = 26           # この範囲に入った邪魔者に飛びかかる
CAT_GUARD_COOL = 5 * FPS
CAT_POUNCE_TIME = 10
CAT_FIND_INTERVAL = 20 * FPS
CAT_FIND_CHANCE = 0.35     # 落とし物を見つける確率。運1につき +0.03
CAT_FIND_LUCK = 0.03

ST_TITLE = 0
ST_PLAY = 1
ST_SHOP = 2
ST_CLEAR = 3

# --- クリア評価 ---------------------------------------------------------------
#   (この秒数未満なら, ランク記号, 称号, 真エンディングに到達するか)
RANKS = [
    (8 * 60, "S", "伝説の採掘士", True),
    (12 * 60, "A", "熟練の採掘士", False),
    (18 * 60, "B", "一人前の採掘士", False),
    (26 * 60, "C", "見習い採掘士", False),
    (10 ** 9, "D", "駆け出しの採掘士", False),
]
TRUE_END_SEC = RANKS[0][0]


# ==============================================================================
#  日本語フォント
#    Pyxel同梱の12pxフォントを使う。10pxより明らかに読みやすい。
# ==============================================================================
def load_jp_font():
    base = os.path.dirname(os.path.abspath(pyxel.__file__))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "examples", "assets", "umplus_j12r.bdf"),
        os.path.join(base, "examples", "assets", "umplus_j10r.bdf"),
        os.path.join(here, "assets", "umplus_j12r.bdf"),
        os.path.join(here, "umplus_j12r.bdf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return pyxel.Font(path)
            except Exception:
                continue
    return None


FONT = None
FONT_H = 12

# ==============================================================================
#  スプライト（maboroshi.pyxres の中の座標）
#    build_assets.py で生成する。Pyxel Editor で直接描き直してもよい。
#      pyxel edit maboroshi.pyxres
# ==============================================================================
RES_FILE = "maboroshi.pyxres"
HAS_SPRITES = False

SPR_MINER = [(0, 0), (16, 0)]          # 立ち / 振り  16x16
SPR_ORE = {                            # 16x16
    "copper": (0, 16), "iron": (16, 16), "silver": (32, 16),
    "gold": (48, 16), "gem": (64, 16),
}
SPR_PHANTOM = [(0, 32), (24, 32)]      # 24x24 明滅の2枚
SPR_FLOOR = [(i * 8, 56) for i in range(4)]   # 8x8
SPR_RUBBLE = [(32 + i * 8, 56) for i in range(3)]
SPR_WALL = (56, 56)
SPR_LADDER = (0, 64)                   # 16x24
COLKEY = 0


def load_resources():
    """スプライトを読み込む。見つからなければ図形描画にそのまま戻る。"""
    global HAS_SPRITES
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, RES_FILE), RES_FILE):
        if os.path.exists(path):
            try:
                pyxel.load(path)
                HAS_SPRITES = True
                return
            except Exception:
                pass
    HAS_SPRITES = False


def text(x, y, s, col):
    pyxel.text(x, y, s, col, FONT)


def text_w(s):
    if FONT is not None:
        return FONT.text_width(s)
    return len(s) * 4


def text_r(right_x, y, s, col):
    """右揃えで描画する。"""
    text(right_x - text_w(s), y, s, col)


def text_center(cx, y, s, col):
    text(cx - text_w(s) // 2, y, s, col)


def text_shadow(x, y, s, col, shadow=0):
    text(x + 1, y + 1, s, shadow)
    text(x, y, s, col)


def text_center_shadow(cx, y, s, col, shadow=0):
    text_shadow(cx - text_w(s) // 2, y, s, col, shadow)


def text_r_shadow(right_x, y, s, col, shadow=0):
    text_shadow(right_x - text_w(s), y, s, col, shadow)


_BIG_CACHE = {}


def text_big(cx, y, s, col, scale=3):
    """オフスクリーンに描いた文字を拡大転送する（内蔵の描画では拡大できないため）。"""
    key = (s, col)
    img = _BIG_CACHE.get(key)
    if img is None:
        w = max(1, text_w(s) + 2)
        h = FONT_H + 3
        img = pyxel.Image(w, h)
        img.cls(0)
        img.text(1, 1, s, col, FONT)
        _BIG_CACHE[key] = img
    pyxel.blt(cx - img.width * scale // 2, y, img, 0, 0, img.width, img.height, 0, scale=scale)


def fmt(n):
    n = int(n)
    if n >= 100000000:
        return f"{n / 100000000:.1f}億"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return f"{n:,}"


def mmss(frames):
    sec = frames // FPS
    return f"{sec // 60}分{sec % 60:02d}秒"


# ==============================================================================
#  データ定義（バランス調整はここだけ触ればよい）
# ==============================================================================
ORE_TYPES = {
    "copper": {"name": "銅鉱石", "hp": 40, "exp": 6, "gold": 10, "col": 9, "dark": 4, "r": 6},
    "iron": {"name": "鉄鉱石", "hp": 220, "exp": 26, "gold": 38, "col": 13, "dark": 5, "r": 7},
    "silver": {"name": "銀鉱石", "hp": 1100, "exp": 95, "gold": 150, "col": 7, "dark": 13, "r": 8},
    "gold": {"name": "金鉱石", "hp": 5200, "exp": 340, "gold": 620, "col": 10, "dark": 9, "r": 9},
    "gem": {"name": "宝石鉱脈", "hp": 18000, "exp": 950, "gold": 2200, "col": 11, "dark": 3, "r": 10},
}
PHANTOM_R = 12

FLOORS = [
    {
        "name": "B1F 銅の坑道", "bg": 1, "rock": 4, "pal": {4: 4, 13: 13, 9: 9},
        "spawn": {"copper": 72, "iron": 24, "silver": 4},
        "boss": "頑固な岩塊", "witch": "おや新入りかい。石でも持っておいで。",
        "ph_hp": 20000, "ph_gold": 2500, "ph_exp": 600, "potion": 2000,
        "pest": {"every": 20, "speed": 1.50, "warn": 24, "max": 1, "linger": False},
        "cat_find": 600,
    },
    {
        "name": "B2F 鉄の坑道", "bg": 1, "rock": 5, "pal": {4: 5, 13: 13, 9: 6},
        "spawn": {"copper": 32, "iron": 46, "silver": 20, "gold": 2},
        "boss": "鉄錆の主", "witch": "ふん、少しは見所があるじゃないか。",
        "ph_hp": 210000, "ph_gold": 26000, "ph_exp": 3500, "potion": 6000,
        "pest": {"every": 18, "speed": 1.65, "warn": 22, "max": 1, "linger": False},
        "cat_find": 1800,
    },
    {
        "name": "B3F 銀の坑道", "bg": 5, "rock": 1, "pal": {4: 5, 13: 6, 9: 7},
        "spawn": {"copper": 10, "iron": 30, "silver": 42, "gold": 16, "gem": 2},
        "boss": "銀霧のぬし", "witch": "深いとこは物入りでね。高いよ。",
        "ph_hp": 2200000, "ph_gold": 210000, "ph_exp": 14000, "potion": 20000,
        "pest": {"every": 16, "speed": 1.80, "warn": 20, "max": 1, "linger": False},
        "cat_find": 6000,
    },
    {
        "name": "B4F 金の坑道", "bg": 4, "rock": 2, "pal": {4: 4, 13: 9, 9: 10},
        "spawn": {"iron": 14, "silver": 34, "gold": 40, "gem": 12},
        "boss": "黄金の巨岩", "witch": "ここまで降りてやってるんだ。",
        "ph_hp": 18000000, "ph_gold": 1600000, "ph_exp": 45000, "potion": 70000,
        "pest": {"every": 14, "speed": 1.90, "warn": 18, "max": 1, "linger": False},
        "cat_find": 20000,
    },
    {
        "name": "B5F 幻の坑道", "bg": 2, "rock": 1, "pal": {4: 2, 13: 14, 9: 14},
        "spawn": {"silver": 20, "gold": 42, "gem": 38},
        "boss": "幻の鉱床", "witch": "最果てだ。……あんた、本気だね。",
        "ph_hp": 160000000, "ph_gold": 0, "ph_exp": 0, "potion": 180000,
        "pest": {"every": 13, "speed": 2.00, "warn": 16, "max": 1, "linger": False},
        "cat_find": 50000,
    },
]

# ピッケルは「順番に買う」必要がない。石で妥協するか鉄まで我慢するかを選べる。
PICKAXES = [
    {"name": "木のピッケル", "mult": 1, "price": 0, "col": 4},
    {"name": "石のピッケル", "mult": 3, "price": 400, "col": 13},
    {"name": "鉄のピッケル", "mult": 9, "price": 4000, "col": 6},
    {"name": "金のピッケル", "mult": 26, "price": 45000, "col": 10},
    {"name": "ダイヤのピッケル", "mult": 75, "price": 400000, "col": 12},
    {"name": "幻のピッケル", "mult": 220, "price": 3500000, "col": 8},#3500000
]

UPGRADES = [
    {"key": "power", "name": "腕力", "desc": "基礎の攻撃力 +4", "base": 150, "rate": 1.17, "max": 60},
    {"key": "speed", "name": "採掘速度", "desc": "自動で振る速さ +2回/秒", "base": 800, "rate": 1.9, "max": 6},
    {"key": "crit", "name": "会心率", "desc": "会心の一撃が出やすくなる", "base": 600, "rate": 1.32, "max": 18},
    {"key": "critdmg", "name": "会心ダメージ", "desc": "会心の一撃が強くなる", "base": 1200, "rate": 1.36, "max": 14},
    {"key": "move", "name": "あしの速さ", "desc": "歩きが楽になる", "base": 350, "rate": 1.5, "max": 6},
    {"key": "luck", "name": "うんの良さ", "desc": "実入りが増え、なにかと運が向く", "base": 900, "rate": 1.34, "max": 16},
]

BASE_MINING_RATE = 6.0     # 押しっぱなしのときの毎秒の振り回数
RATE_PER_SPEED_LV = 2.0


# ==============================================================================
#  演出
# ==============================================================================
class Particle:
    def __init__(self, x, y, col, speed=2.0, life=18, gravity=0.12, size=1):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(speed * 0.3, speed)
        self.x, self.y = x, y
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd - 0.6
        self.col = col
        self.life = self.max_life = life
        self.gravity = gravity
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.vx *= 0.96
        self.life -= 1
        return self.life > 0

    def draw(self):
        col = self.col if self.life > self.max_life * 0.3 else 5
        if self.size <= 1:
            pyxel.pset(self.x, self.y, col)
        else:
            pyxel.rect(self.x, self.y, self.size, self.size, col)


class Popup:
    def __init__(self, x, y, s, col, crit=False):
        self.x = x + random.uniform(-4, 4)
        self.y = y
        self.s = s
        self.col = col
        self.life = 26 if crit else 18
        self.vy = -1.4 if crit else -1.0

    def update(self):
        self.y += self.vy
        self.vy *= 0.9
        self.life -= 1
        return self.life > 0

    def draw(self):
        col = self.col if self.life > 5 else 5
        text_center_shadow(self.x, self.y, self.s, col)


# ==============================================================================
#  鉱石
# ==============================================================================
class Ore:
    def __init__(self, x, y, kind, floor_index, phantom=False):
        self.x, self.y = x, y
        self.kind = kind
        self.phantom = phantom
        self.floor_index = floor_index

        if phantom:
            fl = FLOORS[floor_index]
            self.name = fl["boss"]
            self.max_hp = fl["ph_hp"]
            self.exp = fl["ph_exp"]
            self.gold = fl["ph_gold"]
            self.col, self.dark, self.r = 8, 2, PHANTOM_R
            self.lifetime = random.randint(PHANTOM_LIFETIME_MIN, PHANTOM_LIFETIME_MAX)
        else:
            t = ORE_TYPES[kind]
            self.name = t["name"]
            self.max_hp = t["hp"]
            self.exp = t["exp"]
            self.gold = t["gold"]
            self.col, self.dark, self.r = t["col"], t["dark"], t["r"]
            self.lifetime = random.randint(ORE_LIFETIME_MIN, ORE_LIFETIME_MAX)

        self.hp = self.max_hp
        self.age = 0
        self.hit_shake = 0
        self.hit_once = False

        rng = random.Random(random.getrandbits(32))
        self.speckles = [(math.cos(a) * d, math.sin(a) * d) for a, d in
                         ((rng.uniform(0, math.tau), rng.uniform(0, self.r * 0.65))
                          for _ in range(self.r))]
        self.cracks = [(rng.uniform(0, math.tau), rng.uniform(-0.9, 0.9)) for _ in range(3)]

    @property
    def hp_ratio(self):
        return max(0.0, self.hp / self.max_hp)

    @property
    def remain_frames(self):
        return max(0, self.lifetime - self.age)

    def is_expired(self):
        return self.age > self.lifetime

    def update(self):
        self.age += 1
        if self.hit_shake > 0:
            self.hit_shake -= 1

    def draw(self, targeted=False):
        ox = oy = 0
        if self.hit_shake > 0:
            ox, oy = random.randint(-1, 1), random.randint(-1, 1)
        x, y = self.x + ox, self.y + oy

        if HAS_SPRITES:
            if self.phantom:
                period = 6 if self.remain_frames < PHANTOM_WARN_TIME else 14
                u, v = SPR_PHANTOM[(pyxel.frame_count // period) % 2]
                # 床の色に埋もれないよう、暗い縁を敷いてから描く
                pyxel.circ(x, y, 13, 0)
                pyxel.blt(x - 12, y - 12, 0, u, v, 24, 24, COLKEY)
            else:
                u, v = SPR_ORE[self.kind]
                pyxel.blt(x - 8, y - 8, 0, u, v, 16, 16, COLKEY)
        else:
            col, dark = self.col, self.dark
            if self.phantom:
                period = 6 if self.remain_frames < PHANTOM_WARN_TIME else 14
                col, dark = ((8, 2) if (pyxel.frame_count // period) % 2 == 0 else (14, 1))
            pyxel.circ(x, y, self.r, dark)
            pyxel.circ(x, y, self.r - 1, col)
            for sx, sy in self.speckles:
                pyxel.pset(x + sx, y + sy, dark)
            pyxel.pset(x - self.r * 0.4, y - self.r * 0.45, 7)
            pyxel.pset(x - self.r * 0.4 + 1, y - self.r * 0.45, 7)

        shown = int((1.0 - self.hp_ratio) * 3.99)
        for i in range(min(shown, len(self.cracks))):
            a, bend = self.cracks[i]
            pyxel.line(x + math.cos(a) * self.r * 0.15, y + math.sin(a) * self.r * 0.15,
                       x + math.cos(a + bend * 0.3) * self.r * 0.9,
                       y + math.sin(a + bend * 0.3) * self.r * 0.9, 0)

        if targeted:
            pyxel.circb(x, y, self.r + 2, 7 if (pyxel.frame_count // 4) % 2 == 0 else 10)

        if not self.phantom:
            bw, bx, by = self.r * 2, x - self.r, y - self.r - 5
            pyxel.rect(bx, by, bw, 2, 1)
            pyxel.rect(bx, by, max(0, int(bw * self.hp_ratio)), 2, 11)


# ==============================================================================
#  プレイヤー
# ==============================================================================
class Pest:
    """坑道のコウモリ。一度きりの突進を仕掛けて、外したら飛び去る。

    永久に追尾させると「避ける」が「延命」にしかならず、逃げ続けるだけの作業になる。
    だから狙う時間に上限を置き、さらに近づくほど舵が効かないようにしてある。
    引きつけて横へ抜ければ曲がりきれずに通り過ぎ、そのまま画面の外へ消える。
    つまり避けきればちゃんと報われる。
    当てても鉱石は壊さないし金も奪わない。奪うのはコンボと、避けるための数秒だけ。
    """

    def __init__(self, x, y, speed, warn, linger):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.speed = speed
        self.warn = warn              # 予告の残りフレーム
        self.linger = linger          # 外しても狙い直すか（深層用）
        self.chase = PEST_CHASE_TIME  # 狙っていられる残り時間
        self.age = 0
        self.leave = 0                # 0より大きい間はプレイヤーから離れる
        self.gone = False
        self.dead = False
        self.flap = random.randrange(8)

    def update(self, px, py):
        self.flap += 1
        if self.warn > 0:
            self.warn -= 1
            return

        self.age += 1
        if self.age > PEST_MAX_LIFE:
            self.dead = True
            return

        if self.leave > 0:
            self.leave -= 1
            if self.leave == 0:
                if self.gone:
                    self.dead = True
                    return
                self.chase = PEST_CHASE_TIME    # 居座る個体だけ狙い直す

        if self.chase > 0:
            self.chase -= 1
            dx, dy = px - self.x, py - self.y
            d = math.hypot(dx, dy) or 1.0
            # 近いほど舵を弱める。突進に入ったら曲げられない＝直前の横抜けが通る。
            _, _, lock, accel, _ = pest_tuning()
            steer = accel * min(1.0, d / lock)
            sign = -1.0 if self.leave > 0 else 1.0
            self.vx += dx / d * steer * sign
            self.vy += dy / d * steer * sign
            v = math.hypot(self.vx, self.vy)
            if v > self.speed:
                self.vx = self.vx / v * self.speed
                self.vy = self.vy / v * self.speed
        elif self.vx == 0.0 and self.vy == 0.0:
            self.dead = True
            return

        self.x += self.vx
        self.y += self.vy

        if not (-24 < self.x < SCREEN_W + 24 and FIELD_TOP - 24 < self.y < FIELD_BOTTOM + 24):
            self.dead = True

    @property
    def can_hit(self):
        return self.warn <= 0 and self.leave <= 0

    def on_hit_player(self):
        self.leave = PEST_LEAVE_TIME // 3 if self.linger else PEST_LEAVE_TIME
        self.gone = not self.linger
        self.chase = 0

    def driven_off(self, fx, fy):
        """ネコに追い払われた。もう狙わず、弾かれた向きへ逃げていく。"""
        ang = math.atan2(self.y - fy, self.x - fx)
        self.vx = math.cos(ang) * self.speed * 1.8
        self.vy = math.sin(ang) * self.speed * 1.8
        self.chase = 0
        self.leave = PEST_LEAVE_TIME
        self.gone = True

    def draw(self):
        x, y = int(self.x), int(self.y)
        if self.warn > 0:
            # 予告。「ここから来るぞ」だけを見せる。姿はまだ出さない。
            if (self.warn // 3) % 2 == 0:
                r = pest_tuning()[1]
                pyxel.circb(x, y, r // 2, 8)
                pyxel.circb(x, y, 2, 8)
            return

        # 胴と、羽ばたく翼。色13は坑道のどの床色に対しても沈まない。
        # 翼の端を当たり判定に合わせる。見えている大きさと当たる大きさを一致させる。
        r = pest_tuning()[1]
        b = max(2, r // 4)
        wy = -(r // 3) if (self.flap // 4) % 2 == 0 else r // 5
        pyxel.tri(x - b, y - 1, x - r, y + wy, x - b - 1, y + b, 13)
        pyxel.tri(x + b, y - 1, x + r, y + wy, x + b + 1, y + b, 13)
        pyxel.circ(x, y, b, 13)
        pyxel.pset(x - b + 1, y - 1, 8)
        pyxel.pset(x + b - 1, y - 1, 8)


#   ネコのドット絵。# = 体、o = 目、= = 鼻と内耳、右向きで描いてある。
#   身体を張るところではないので、ここは素直に見た目だけを取る。
CAT_W = 9
CAT_COLS = {".": None, "#": 10, "o": 0, "=": 4}
CAT_SIT = (
    "...#...#.",
    "...##.##.",
    "...#####.",
    "..#o#=#o#",
    "..#######",
    ".########",
    ".########",
    ".##...##.",
)
CAT_BLINK = (
    "...#...#.",
    "...##.##.",
    "...#####.",
    "..#=#=#=#",
    "..#######",
    ".########",
    ".########",
    ".##...##.",
)
CAT_LEAP = (
    ".........",
    "...#...#.",
    "...##.##.",
    "...#o#o#.",
    "#########",
    "#########",
    "##.....##",
    "#.......#",
)


class Cat:
    """ほりほりネコ。

    掘りは手伝わない。邪魔者に飛びかかって追い払い、たまに落とし物を見つけてくる。
    どちらもクールタイムと確率がついていて、万能にはしていない。
    そもそもこのネコの本当の役目は、坑道にネコがいるという、それだけのことにある。
    """

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.face = 1
        self.guard_cool = 0
        self.find_timer = CAT_FIND_INTERVAL
        self.pounce = 0             # 飛びかかりの残りフレーム
        self.tx = self.ty = 0.0     # 飛びかかる先

    def update(self, owner):
        if self.guard_cool > 0:
            self.guard_cool -= 1
        if self.pounce > 0:
            self.pounce -= 1
            self.x += (self.tx - self.x) * 0.34
            self.y += (self.ty - self.y) * 0.34
            return

        dx, dy = owner.x - self.x, owner.y - self.y
        d = math.hypot(dx, dy)
        if d > CAT_FOLLOW_DIST:
            # 離されたら小走りになる。追いつけば座って待つ。
            sp = CAT_SPEED * (1.7 if d > 56 else 1.0)
            self.x += dx / d * min(sp, d)
            self.y += dy / d * min(sp, d)
            if abs(dx) > 1.0:
                self.face = 1 if dx > 0 else -1

    @property
    def can_guard(self):
        return self.guard_cool <= 0 and self.pounce <= 0

    def leap(self, tx, ty):
        self.pounce = CAT_POUNCE_TIME
        self.tx, self.ty = tx, ty
        self.guard_cool = CAT_GUARD_COOL
        if abs(tx - self.x) > 1.0:
            self.face = 1 if tx > self.x else -1

    def draw(self):
        x, y = int(self.x), int(self.y)
        f = self.face
        rows = CAT_LEAP if self.pounce > 0 else (
            CAT_SIT if (pyxel.frame_count // 20) % 8 else CAT_BLINK)
        ox = x - (CAT_W // 2)
        oy = y - (len(rows) - 3)
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                c = CAT_COLS.get(ch)
                if c is not None:
                    # 左を向くときは左右反転して描く
                    pyxel.pset(ox + (rx if f > 0 else CAT_W - 1 - rx), oy + ry, c)

        # しっぽ。座っているあいだだけ、ゆっくり振る。細いと糸に見えるので2px。
        if self.pounce <= 0:
            bx = ox + (1 if f > 0 else CAT_W - 2)
            ty = oy + 4 + int(math.sin(pyxel.frame_count * 0.10) * 2)
            pyxel.line(bx, oy + 6, bx - f * 3, ty, 10)
            pyxel.line(bx, oy + 7, bx - f * 3, ty + 1, 10)


class Player:
    def __init__(self):
        self.x = SCREEN_W / 2
        self.y = (FIELD_TOP + FIELD_BOTTOM) / 2
        self.level = 1
        self.exp = 0
        self.gold = 0
        self.owned = {0}          # 所持しているピッケルの番号
        self.potions = 0
        self.potions_bought = 0    # 今いるフロアで買った数
        self.buff_end = -1
        self.buff_mult = 1.0       # 飲んだときに決まる
        self.combo = 0
        self.last_hit_frame = -999
        self.upgrades = {u["key"]: 0 for u in UPGRADES}
        self.total_mined = 0
        self.swing = 0
        self.face = 1
        self.mine_charge = 0.0
        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP
        self.invuln = 0
        self.kbx = self.kby = 0.0   # 弾かれた勢い

    @property
    def pickaxe(self):
        """所持している中で最も強いピッケルを自動的に使う。"""
        return max(self.owned)

    @property
    def exp_to_next(self):
        return int(22 * (self.level ** 1.85))

    @property
    def base_attack(self):
        return 8 + (self.level - 1) * 3 + self.upgrades["power"] * 4

    @property
    def crit_rate(self):
        # 幸運はここにもわずかに効く（説明には書いていない）
        return min(0.9, 0.03 + self.upgrades["crit"] * 0.03 + self.upgrades["luck"] * 0.005)

    @property
    def crit_mult(self):
        return 2.0 + self.upgrades["critdmg"] * 0.4

    @property
    def combo_mult(self):
        return 1.0 + min(self.combo, COMBO_MAX) * 0.01

    @property
    def buff_active(self):
        return pyxel.frame_count < self.buff_end

    @property
    def mining_rate(self):
        """押しっぱなしのときの毎秒の振り回数。手動連打はこれを超えられる。"""
        return BASE_MINING_RATE + self.upgrades["speed"] * RATE_PER_SPEED_LV

    @property
    def move_speed(self):
        # 上げすぎると鉱石を殴りきる前に通り過ぎてしまうので、伸びは控えめにする
        return 2.2 + self.upgrades["move"] * 0.22

    @property
    def gold_mult(self):
        return 1.0 + self.upgrades["luck"] * 0.08

    def attack_damage(self, crit):
        dmg = self.base_attack * PICKAXES[self.pickaxe]["mult"] * self.combo_mult
        if self.buff_active:
            dmg *= self.buff_mult
        if crit:
            dmg *= self.crit_mult
        return int(dmg)

    @property
    def average_dps(self):
        """幻に挑めるかの判定用。押しっぱなしを基準に、会心の期待値を込みで概算する。"""
        dmg = self.base_attack * PICKAXES[self.pickaxe]["mult"]
        dmg *= 1.0 + min(COMBO_MAX, 60) * 0.01
        dmg *= 1.0 + self.crit_rate * (self.crit_mult - 1.0)
        if self.buff_active:
            dmg *= self.buff_mult
        return dmg * self.mining_rate

    def gain_exp(self, amount):
        self.exp += amount
        levels = 0
        while self.exp >= self.exp_to_next:
            self.exp -= self.exp_to_next
            self.level += 1
            levels += 1
        return levels

    def move(self):
        vx = vy = 0
        if pyxel.btn(pyxel.KEY_LEFT):
            vx -= 1
        if pyxel.btn(pyxel.KEY_RIGHT):
            vx += 1
        if pyxel.btn(pyxel.KEY_UP):
            vy -= 1
        if pyxel.btn(pyxel.KEY_DOWN):
            vy += 1
        if vx or vy:
            d = math.hypot(vx, vy)
            self.x += vx / d * self.move_speed
            self.y += vy / d * self.move_speed
            if vx:
                self.face = 1 if vx > 0 else -1
        # ノックバックは入力とは別に乗せる。操作不能にはせず、押し戻されるだけ。
        if abs(self.kbx) > 0.05 or abs(self.kby) > 0.05:
            self.x += self.kbx
            self.y += self.kby
            self.kbx *= 0.80
            self.kby *= 0.80
        else:
            self.kbx = self.kby = 0.0
        self.x = max(5, min(SCREEN_W - 5, self.x))
        self.x = max(12, min(SCREEN_W - 12, self.x))
        self.y = max(FIELD_TOP + 14, min(FIELD_BOTTOM - 14, self.y))

    def update_combo(self):
        if pyxel.frame_count - self.last_hit_frame > COMBO_TIMEOUT:
            self.combo = 0
        if self.swing > 0:
            self.swing -= 1
        if self.invuln > 0:
            self.invuln -= 1

    def draw(self):
        # 無敵の間は点滅させる。何が起きたかを一目で分からせる。
        if self.invuln > 0 and (pyxel.frame_count // 2) % 2 == 0:
            return
        x, y = int(self.x), int(self.y)
        if HAS_SPRITES:
            u, v = SPR_MINER[1 if self.swing > 0 else 0]
            # 幅を負にすると左右反転して描ける
            pyxel.blt(x - 8, y - 9, 0, u, v, 16 * self.face, 16, COLKEY)
        else:
            pyxel.rect(x - 3, y - 4, 6, 8, 12)
            pyxel.rect(x - 4, y - 6, 8, 3, 10)
            pyxel.pset(x + self.face, y - 6, 7)
            pyxel.rect(x - 3, y + 4, 2, 2, 1)
            pyxel.rect(x + 1, y + 4, 2, 2, 1)
        px = x + self.face * 5
        if self.swing > 0:
            head_x, head_y = px + self.face * 3, y - 1
        else:
            head_x, head_y = px + self.face * 1, y - 7
        pyxel.line(px, y - 1, head_x, head_y, 4)
        pyxel.pset(head_x, head_y, PICKAXES[self.pickaxe]["col"])
        pyxel.pset(head_x + self.face, head_y, PICKAXES[self.pickaxe]["col"])


# ==============================================================================
#  本体
# ==============================================================================
class App:
    def __init__(self):
        global FONT
        pyxel.init(SCREEN_W, SCREEN_H, title="幻鉱 -MABOROSHI-", fps=FPS)
        FONT = load_jp_font()
        load_resources()
        self.setup_sounds()
        self.bgm_on = True
        self.state = ST_TITLE
        self.reset()
        pyxel.run(self.update, self.draw)

    def reset(self):
        self.player = Player()
        self.floor_index = 0
        self.ores = []
        self.pests = []
        self.pest_timer = 0
        self.cat = None
        self.particles = []
        self.popups = []
        self.ladder = None
        self.shake = 0.0
        self.shake_ang = 0.0
        self.message = ""
        self.message_col = 7
        self.message_timer = 0
        self.phantom_cooldown = 0
        self.phantom_defeated = set()
        self.shop_cursor = 0
        self.shop_scroll = 0
        self.play_frames = 0
        self.clear_page = 0
        self.rank = None
        self.build_background()

    def build_background(self):
        """洞窟の床を8x8タイルで敷き詰め、ふちを岩壁で囲む。階層ごとの配置は固定。"""
        fl = FLOORS[self.floor_index]
        rng = random.Random(self.floor_index * 7919)
        self.tiles = []       # (x, y, スプライト番号)
        self.rubble = []      # (x, y, スプライト番号)
        for ty in range(FIELD_TOP, FIELD_BOTTOM, 8):
            for tx in range(0, SCREEN_W, 8):
                self.tiles.append((tx, ty, rng.randrange(len(SPR_FLOOR))))
        for _ in range(22):
            # グリッドに乗せると模様に見えるので、わざと半端な位置に置く
            x = rng.randint(10, SCREEN_W - 18)
            y = rng.randint(FIELD_TOP + 10, FIELD_BOTTOM - 18)
            self.rubble.append((x, y, rng.randrange(len(SPR_RUBBLE))))
        # 図形描画に落ちたときのための予備
        self.bg_dots = [(rng.randint(0, SCREEN_W - 1), rng.randint(FIELD_TOP, FIELD_BOTTOM - 1),
                         13 if rng.random() < 0.08 else fl["rock"]) for _ in range(130)]

    # --- 音 -----------------------------------------------------------------
    #   Pyxelの発音チャンネルは0〜3の4本しかない。
    #   効果音を ch0/ch1、BGMを ch2/ch3 に分けないと、採掘のたびにBGMが止まる。
    def setup_sounds(self):
        s = pyxel.sounds
        s[0].set("a3", "p", "2", "f", 5)                        # 採掘ヒット
        s[1].set("c4f4", "s", "43", "f", 5)                     # 会心の一撃
        s[2].set("f2c2", "n", "65", "f", 8)                     # 鉱石を壊した
        s[3].set("c3e3g3c4", "t", "6666", "n", 7)               # レベルアップ
        s[4].set("e3b3e4", "s", "544", "n", 8)                  # 購入・入手
        s[5].set("c2g1c1", "t", "777", "v", 22)                 # 幻が現れた
        s[6].set("c3g2e2c2", "t", "6543", "f", 16)              # 幻が消えた
        s[7].set("g2c3e3g3c4e4g4c4", "t", "77777777", "n", 9)   # 階層移動・クリア
        s[8].set("a3", "n", "3", "f", 12)                       # コウモリの気配
        s[9].set("c2g1", "n", "76", "f", 10)                    # 弾かれた
        s[10].set("e4a4", "s", "43", "n", 7)                    # ネコが飛びかかった

        s[20].set("c1rrrg1rrra1rrrf1rrr", "t", "6", "n", 26)    # BGM ベース
        s[21].set("rrc2rrg2rrra2rrf2rr", "p", "5", "f", 26)     # BGM 上モノ
        pyxel.musics[0].set([], [], [20], [21])

    def start_bgm(self):
        if self.bgm_on:
            pyxel.playm(0, loop=True)

    def toggle_bgm(self):
        self.bgm_on = not self.bgm_on
        if self.bgm_on:
            pyxel.playm(0, loop=True)
        else:
            pyxel.stop()

    # ==========================================================================
    #  更新
    # ==========================================================================
    def update(self):
        if pyxel.btnp(pyxel.KEY_M):
            self.toggle_bgm()

        if self.state == ST_TITLE:
            self.update_title()
        elif self.state == ST_PLAY:
            self.update_play()
        elif self.state == ST_SHOP:
            self.update_shop()
        elif self.state == ST_CLEAR:
            self.update_clear()

        self.particles = [p for p in self.particles if p.update()]
        self.popups = [p for p in self.popups if p.update()]
        if self.shake > 0.0:
            self.shake *= SHAKE_DECAY
            if self.shake < SHAKE_MIN:
                self.shake = 0.0
        if self.message_timer > 0:
            self.message_timer -= 1

    def update_title(self):
        if pyxel.btnp(pyxel.KEY_Z) or pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            self.reset()
            self.state = ST_PLAY
            self.start_bgm()

    def update_play(self):
        self.play_frames += 1
        p = self.player
        p.move()
        p.update_combo()

        for o in self.ores:
            o.update()
        self.expire_ores()

        if pyxel.frame_count % ORE_SPAWN_INTERVAL == 0:
            self.try_spawn()
        if self.phantom_cooldown > 0:
            self.phantom_cooldown -= 1

        self.handle_mining()
        self.update_pests()
        self.update_cat()

        if TUNING:
            for i in range(len(PEST_PRESETS)):
                if pyxel.btnp(pyxel.KEY_1 + i):
                    globals()["PEST_LEVEL"] = i
                    self.set_message(f"コウモリ: {PEST_PRESETS[i][0]}", 14)
        if pyxel.btnp(pyxel.KEY_C):
            self.use_potion()
        if pyxel.btnp(pyxel.KEY_S):
            self.state = ST_SHOP
            self.shop_cursor = 0
            self.shop_scroll = 0
        if pyxel.btnp(pyxel.KEY_X):
            self.try_descend()

    def handle_mining(self):
        """押した瞬間は必ず1回振る。押しっぱなしの間は毎秒 mining_rate 回まで自動で振る。
        つまり手動連打は自動連打より速くできるので、連打がそのまま腕前になる。"""
        p = self.player
        target = self.find_target()

        if pyxel.btnp(pyxel.KEY_Z):
            p.mine_charge = 0.0
            if target is not None:
                self.mine(target)
        elif pyxel.btn(pyxel.KEY_Z):
            p.mine_charge += p.mining_rate / FPS
            while p.mine_charge >= 1.0:
                p.mine_charge -= 1.0
                if target is None:
                    break
                self.mine(target)
                if target.hp <= 0:
                    break
        else:
            p.mine_charge = 0.0

    # --- 邪魔者 -------------------------------------------------------------
    def update_pests(self):
        p = self.player
        cfg = FLOORS[self.floor_index]["pest"]

        self.pest_timer -= 1
        if self.pest_timer <= 0:
            self.spawn_pest(cfg)
            self.pest_timer = self.pest_interval(cfg)

        for q in self.pests:
            q.update(p.x, p.y)
            if (q.can_hit and p.invuln <= 0
                    and math.hypot(q.x - p.x, q.y - p.y) < pest_tuning()[1]):
                self.hit_player(q)
        self.pests = [q for q in self.pests if not q.dead]

    def pest_interval(self, cfg):
        """運が高いほど間隔が空く。説明はしない。"""
        lv = self.player.upgrades["luck"]
        return int(cfg["every"] * FPS * (1.0 + lv * PEST_LUCK_INTERVAL))

    def spawn_pest(self, cfg):
        """盤面のふちから湧かせる。プレイヤーの真横には出さない。"""
        if len(self.pests) >= cfg["max"]:
            return
        pos = None
        for _ in range(20):
            if random.random() < 0.5:
                x = random.choice([12, SCREEN_W - 12])
                y = random.randint(FIELD_TOP + 14, FIELD_BOTTOM - 14)
            else:
                x = random.randint(14, SCREEN_W - 14)
                y = random.choice([FIELD_TOP + 12, FIELD_BOTTOM - 12])
            if math.hypot(x - self.player.x, y - self.player.y) > 44:
                pos = (x, y)
                break
        if pos is None:
            return
        lv = self.player.upgrades["luck"]
        warn = int(cfg["warn"] + lv * PEST_LUCK_WARN)
        self.pests.append(Pest(pos[0], pos[1], cfg["speed"] * pest_tuning()[4],
                               warn, cfg["linger"]))
        pyxel.play(1, 8)

    # --- ほりほりネコ -------------------------------------------------------
    def update_cat(self):
        if self.cat is None:
            return
        p = self.player
        cat = self.cat
        cat.update(p)

        # 邪魔者に飛びかかる。クールタイムがあるので、群れは捌けない。
        if cat.can_guard:
            for q in self.pests:
                if not q.can_hit:
                    continue
                if math.hypot(q.x - cat.x, q.y - cat.y) < CAT_GUARD_R:
                    cat.leap(q.x, q.y)
                    q.driven_off(cat.x, cat.y)
                    for _ in range(6):
                        self.particles.append(Particle(q.x, q.y, 10, speed=2.2, life=14))
                    pyxel.play(0, 10)
                    break

        # 落とし物。運が高いほど見つけるし、見つける額も増える（gold_multが乗る）。
        cat.find_timer -= 1
        if cat.find_timer <= 0:
            cat.find_timer = CAT_FIND_INTERVAL
            lv = p.upgrades["luck"]
            if random.random() < CAT_FIND_CHANCE + lv * CAT_FIND_LUCK:
                base = FLOORS[self.floor_index]["cat_find"]
                gold = int(base * random.uniform(0.7, 1.6) * p.gold_mult)
                p.gold += gold
                self.popups.append(Popup(cat.x, cat.y - 10, f"+{fmt(gold)}", 10))
                self.set_message(f"ラッキー！ ネコが {fmt(gold)} を見つけた", 10)
                pyxel.play(1, 4)

    def hit_player(self, pest):
        """本体の罰はHPではなくコンボ。0.67秒で切れるので、弾かれた時点で確定で飛ぶ。"""
        p = self.player
        p.hp -= 1
        p.invuln = PLAYER_INVULN
        p.combo = 0
        p.last_hit_frame = -999
        p.mine_charge = 0.0

        ang = math.atan2(p.y - pest.y, p.x - pest.x)
        p.kbx = math.cos(ang) * PEST_KNOCKBACK
        p.kby = math.sin(ang) * PEST_KNOCKBACK
        pest.on_hit_player()

        for _ in range(6):
            self.particles.append(Particle(p.x, p.y, 8, speed=2.0, life=14))
        self.add_shake(SHAKE_HIT)
        pyxel.play(1, 9)

        if p.hp <= 0:
            self.on_player_down()
        else:
            self.set_message("邪魔された！ コンボが切れた", 8)

    def on_player_down(self):
        """HPが尽きた。B1〜B5では1階層戻されるだけで、装備も金も強化もそのまま残る。
        失うのは時間だけ。タイムで評価されるこのゲームでは、それで十分に重い。"""
        p = self.player
        p.hp = p.max_hp
        p.invuln = PLAYER_INVULN * 2
        p.kbx = p.kby = 0.0
        p.combo = 0
        self.pests = []
        self.ores = []
        self.phantom_cooldown = PHANTOM_COOLDOWN
        self.pest_timer = self.pest_interval(FLOORS[self.floor_index]["pest"])
        self.add_shake(SHAKE_PHANTOM)
        pyxel.play(1, 6)

        if self.floor_index > 0:
            self.floor_index -= 1
            self.build_background()
            # 一度抜けた階なので、ハシゴは見つかったままにしておく
            self.ladder = None
            self.spawn_ladder(SCREEN_W / 2, (FIELD_TOP + FIELD_BOTTOM) / 2)
            self.set_message("力尽きた… " + FLOORS[self.floor_index]["name"] + " まで戻された", 8)
        else:
            self.set_message("力尽きた… 掘りかけの鉱石が崩れた", 8)

        p.x = SCREEN_W / 2
        p.y = (FIELD_TOP + FIELD_BOTTOM) / 2

    def expire_ores(self):
        alive = []
        for o in self.ores:
            if o.is_expired():
                if o.phantom:
                    self.on_phantom_escape(o)
                else:
                    for _ in range(4):
                        self.particles.append(Particle(o.x, o.y, 5, speed=1.0, life=12))
            else:
                alive.append(o)
        self.ores = alive

    # --- スポーン -----------------------------------------------------------
    def try_spawn(self):
        fl = FLOORS[self.floor_index]
        has_phantom = any(o.phantom for o in self.ores)

        if (not has_phantom and self.phantom_cooldown <= 0
                and random.random() < PHANTOM_SPAWN_CHANCE):
            pos = self.find_spawn_pos(PHANTOM_R)
            if pos:
                boss = Ore(pos[0], pos[1], None, self.floor_index, phantom=True)
                # 幸運は主が留まる時間も伸ばす。運を鍛える道にも勝ち筋がある。
                boss.lifetime = int(boss.lifetime * (1.0 + self.player.upgrades["luck"] * 0.02))
                self.ores.append(boss)
                pyxel.play(1, 5)
                self.set_message(f"{boss.name}が現れた…！", 8)
                return

        if len([o for o in self.ores if not o.phantom]) >= MAX_ORE_ON_SCREEN:
            return
        kind = self.weighted_kind(fl["spawn"])
        pos = self.find_spawn_pos(ORE_TYPES[kind]["r"])
        if pos:
            self.ores.append(Ore(pos[0], pos[1], kind, self.floor_index))

    @staticmethod
    def weighted_kind(table):
        r = random.uniform(0, sum(table.values()))
        upto = 0
        for kind, w in table.items():
            upto += w
            if r <= upto:
                return kind
        return list(table)[-1]

    def find_spawn_pos(self, radius):
        for _ in range(30):
            x = random.randint(radius + 10, SCREEN_W - radius - 10)
            y = random.randint(FIELD_TOP + radius + 10, FIELD_BOTTOM - radius - 10)
            if math.hypot(x - self.player.x, y - self.player.y) < 32:
                continue
            if self.ladder and math.hypot(x - self.ladder[0], y - self.ladder[1]) < radius + 14:
                continue
            if any(math.hypot(x - o.x, y - o.y) < radius + o.r + 3 for o in self.ores):
                continue
            return (x, y)
        return None

    # --- 採掘 ---------------------------------------------------------------
    def find_target(self):
        best, best_d = None, 1e9
        for o in self.ores:
            d = math.hypot(o.x - self.player.x, o.y - self.player.y) - o.r
            if d <= MINE_REACH and d < best_d:
                best, best_d = o, d
        return best

    def mine(self, ore):
        p = self.player
        p.swing = 4
        p.combo += 1
        p.last_hit_frame = pyxel.frame_count
        p.face = 1 if ore.x >= p.x else -1

        crit = random.random() < p.crit_rate
        dmg = p.attack_damage(crit)
        first_hit = not ore.hit_once
        ore.hit_once = True
        ore.hp -= dmg
        ore.hit_shake = 3

        ang = math.atan2(p.y - ore.y, p.x - ore.x)
        hx, hy = ore.x + math.cos(ang) * ore.r, ore.y + math.sin(ang) * ore.r
        for _ in range(6 if crit else 3):
            self.particles.append(Particle(hx, hy, 10 if crit else ore.col, speed=2.2, life=12))

        if crit:
            pyxel.play(0, 1)
            self.popups.append(Popup(ore.x, ore.y - ore.r - 4, f"会心 {fmt(dmg)}", 10, crit=True))
        else:
            pyxel.play(0, 0)
            self.popups.append(Popup(ore.x, ore.y - ore.r - 4, fmt(dmg), 7))

        if ore.phantom and first_hit:
            self.judge_phantom(ore)
        if ore.hp <= 0:
            self.break_ore(ore)

    def judge_phantom(self, ore):
        """勝てるかどうかは教えない。ゲージが動くかどうかという、見れば分かる情報だけ返す。"""
        five_sec = self.player.average_dps * 5
        if five_sec < ore.max_hp * 0.02:
            self.set_message("ビクともしない…！", 8)
        else:
            self.set_message("硬い…！だが、確かに削れている", 10)

    def break_ore(self, ore):
        p = self.player
        if ore in self.ores:
            self.ores.remove(ore)

        for _ in range(20 if ore.phantom else 10):
            self.particles.append(
                Particle(ore.x, ore.y, ore.col, speed=3.4, life=26, size=2 if ore.phantom else 1))
        self.add_shake(SHAKE_PHANTOM if ore.phantom else SHAKE_BREAK)

        if ore.phantom:
            self.on_phantom_break(ore)
            return

        pyxel.play(1, 2)
        gold = int(ore.gold * p.gold_mult)
        p.gold += gold
        p.total_mined += 1
        levels = p.gain_exp(ore.exp)
        self.popups.append(Popup(ore.x, ore.y - 10, f"+{fmt(gold)}", 10))

        if levels:
            pyxel.play(1, 3)
            self.set_message(f"レベルアップ！  Lv.{p.level}", 11)
            for _ in range(14):
                self.particles.append(Particle(p.x, p.y, 11, speed=2.6, life=24))

    def on_phantom_break(self, ore):
        p = self.player
        self.phantom_cooldown = PHANTOM_COOLDOWN

        if self.floor_index == len(FLOORS) - 1:
            pyxel.stop()
            pyxel.play(1, 7)
            self.rank = self.judge_rank()
            self.clear_page = 0
            self.state = ST_CLEAR
            return

        pyxel.play(1, 7)
        first = self.floor_index not in self.phantom_defeated
        self.phantom_defeated.add(self.floor_index)
        gold = int(ore.gold * p.gold_mult)
        p.gold += gold
        p.gain_exp(ore.exp)
        self.popups.append(Popup(ore.x, ore.y - 14, f"+{fmt(gold)}", 10, crit=True))

        if first:
            self.spawn_ladder(ore.x, ore.y)
            self.set_message(f"{ore.name}を砕いた！ 下への道が開けた", 11)
        else:
            self.set_message(f"{ore.name}を砕いた！  +{fmt(gold)}", 11)

    def on_phantom_escape(self, ore):
        self.phantom_cooldown = PHANTOM_COOLDOWN
        pyxel.play(1, 6)
        if ore.hp_ratio >= 0.999:
            self.set_message(f"{ore.name}は岩壁の奥へ消えた…", 13)
        else:
            self.set_message(f"あと{int(ore.hp_ratio * 100)}%だった…消えてしまった", 13)
        for _ in range(16):
            self.particles.append(Particle(ore.x, ore.y, 2, speed=1.6, life=24))

    def judge_rank(self):
        sec = self.play_frames // FPS
        for limit, mark, title, is_true in RANKS:
            if sec < limit:
                return (mark, title, is_true)
        return RANKS[-1][1:]

    # --- 階層移動 -----------------------------------------------------------
    def spawn_ladder(self, near_x, near_y):
        """「[X]降りる」の文字が盤面の上端で切れないよう、出現位置を下寄りに限定する。"""
        if self.ladder is not None:
            return
        top = FIELD_TOP + 42
        pos = None
        for _ in range(40):
            cand = self.find_spawn_pos(10)
            if cand and cand[1] >= top:
                pos = cand
                break
        if pos is None:
            pos = (max(20, min(SCREEN_W - 20, int(near_x))),
                   random.randint(top, FIELD_BOTTOM - 20))
        self.ladder = pos
        pyxel.play(1, 4)

    def try_descend(self):
        if self.ladder is None:
            return
        if math.hypot(self.player.x - self.ladder[0], self.player.y - self.ladder[1]) > 14:
            return
        self.floor_index += 1
        self.ladder = None
        self.ores = []
        self.pests = []
        self.phantom_cooldown = PHANTOM_COOLDOWN // 2
        # 降りた直後は必ず一息つける。降りた瞬間に殴られるのは理不尽なので。
        self.pest_timer = self.pest_interval(FLOORS[self.floor_index]["pest"])
        self.player.hp = self.player.max_hp
        self.player.potions_bought = 0
        self.player.kbx = self.player.kby = 0.0
        self.player.x = SCREEN_W / 2
        self.player.y = (FIELD_TOP + FIELD_BOTTOM) / 2
        if self.cat is not None:
            self.cat.x = self.player.x - 15
            self.cat.y = self.player.y + 4
            self.cat.pounce = 0
        self.build_background()
        pyxel.play(1, 7)
        self.set_message(FLOORS[self.floor_index]["name"] + " へ降りた", 11)
        for _ in range(24):
            self.particles.append(Particle(self.player.x, self.player.y, 13, speed=2.4, life=26))

    def use_potion(self):
        p = self.player
        if p.potions <= 0:
            self.set_message("怪しい薬を持っていない", 13)
            return
        p.potions -= 1
        mult, sec = self.roll_potion()
        p.buff_mult = mult
        p.buff_end = pyxel.frame_count + int(sec * FPS)
        pyxel.play(1, 4)

        # 何が出たかは、引きの良し悪しごと言葉で返す。数字だけより悔しさが残る。
        if mult >= 3.0:
            msg, col = f"身体が燃えるようだ！  x{mult} ({int(sec)}秒)", 10
        elif mult >= 2.5:
            msg, col = f"力がみなぎる！  x{mult} ({int(sec)}秒)", 10
        elif mult >= 2.0:
            msg, col = f"効いてきた  x{mult} ({int(sec)}秒)", 11
        else:
            msg, col = f"……気のせいか？  x{mult} ({int(sec)}秒)", 13
        self.set_message(msg, col)
        for _ in range(18 if mult >= 2.5 else 8):
            self.particles.append(Particle(p.x, p.y, 10, speed=2.4, life=22))

    def roll_potion(self):
        """効き目を引く。運は良い段の出やすさと、効いている長さの両方に効く。"""
        lv = self.player.upgrades["luck"]
        weights = [max(1.0, base + lv * per) for _, base, per in POTION_TIERS]
        r = random.uniform(0, sum(weights))
        mult = POTION_TIERS[-1][0]
        for (m, _, _), w in zip(POTION_TIERS, weights):
            if r < w:
                mult = m
                break
            r -= w
        # 運が高いほど長い方へ寄せる
        t = random.random() ** (1.0 / (1.0 + lv * POTION_LUCK_SEC))
        sec = POTION_SEC_MIN + (POTION_SEC_MAX - POTION_SEC_MIN) * t
        return mult, round(sec)

    # --- ショップ -----------------------------------------------------------
    def potion_price(self):
        return FLOORS[self.floor_index]["potion"]

    def shop_items(self):
        """ピッケルは全種を並べる。石で妥協するか鉄まで貯めるかを自分で選べる。"""
        p = self.player
        items = []
        for i, pk in enumerate(PICKAXES):
            if i == 0:
                continue
            if i in p.owned:
                items.append({"type": "pickaxe", "idx": i, "label": pk["name"],
                              "sub": "しょゆう済み", "price": None, "col": pk["col"]})
            else:
                items.append({"type": "pickaxe", "idx": i, "label": pk["name"],
                              "sub": f"攻撃力 x{pk['mult']}", "price": pk["price"],
                              "col": pk["col"]})
        for u in UPGRADES:
            lv = p.upgrades[u["key"]]
            if lv >= u["max"]:
                items.append({"type": "upgrade", "key": u["key"], "label": f"{u['name']}（最大）",
                              "sub": u["desc"], "price": None, "col": 6})
            else:
                items.append({"type": "upgrade", "key": u["key"],
                              "label": f"{u['name']}  Lv.{lv}/{u['max']}",
                              "sub": u["desc"], "price": int(u["base"] * (u["rate"] ** lv)),
                              "col": 6})
        if self.cat is None:
            items.append({"type": "cat", "label": "ほりほりネコ",
                          "sub": "ついてくる。邪魔者を追い払う", "price": CAT_PRICE, "col": 10})
        left = POTION_PER_FLOOR - p.potions_bought
        items.append({"type": "potion",
                      "label": f"怪しい薬（所持 {p.potions}）",
                      "sub": ("飲むまで効き目はわからない"
                              if left > 0 else "この階ではもう売ってくれない"),
                      "price": self.potion_price() if left > 0 else None, "col": 10})
        return items

    SHOP_ROWS = 6

    def update_shop(self):
        items = self.shop_items()
        n = len(items)
        self.shop_cursor = max(0, min(self.shop_cursor, n - 1))
        if pyxel.btnp(pyxel.KEY_DOWN, 12, 4):
            self.shop_cursor = (self.shop_cursor + 1) % n
        if pyxel.btnp(pyxel.KEY_UP, 12, 4):
            self.shop_cursor = (self.shop_cursor - 1) % n
        # カーソルが見える位置までリストをスクロールする
        self.shop_scroll = max(min(self.shop_scroll, self.shop_cursor),
                               self.shop_cursor - self.SHOP_ROWS + 1)
        self.shop_scroll = max(0, min(self.shop_scroll, max(0, n - self.SHOP_ROWS)))
        if pyxel.btnp(pyxel.KEY_Z) or pyxel.btnp(pyxel.KEY_RETURN):
            self.buy(items[self.shop_cursor])
        if pyxel.btnp(pyxel.KEY_S) or pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.state = ST_PLAY

    def buy(self, item):
        p = self.player
        price = item["price"]
        if price is None:
            self.set_message("これ以上は買えない", 13)
            return
        if p.gold < price:
            self.set_message("お金が足りない…", 8)
            return

        p.gold -= price
        pyxel.play(1, 4)
        if item["type"] == "pickaxe":
            before = p.pickaxe
            p.owned.add(item["idx"])
            if p.pickaxe != before:
                self.set_message(f"{PICKAXES[p.pickaxe]['name']} を手に入れた！", 11)
            else:
                self.set_message(f"{PICKAXES[item['idx']]['name']} を手に入れた", 11)
        elif item["type"] == "upgrade":
            p.upgrades[item["key"]] += 1
            self.set_message(f"{item['label'].split()[0]} を強化した！", 11)
        elif item["type"] == "cat":
            self.cat = Cat(p.x - p.face * 15, p.y + 4)
            self.set_message("ほりほりネコが ついてきた！", 11)
        else:
            p.potions += 1
            p.potions_bought += 1
            left = POTION_PER_FLOOR - p.potions_bought
            self.set_message(f"怪しい薬を買った（この階であと{left}本）", 11)

    def update_clear(self):
        mark, title, is_true = self.rank
        if is_true and self.clear_page == 0:
            if pyxel.btnp(pyxel.KEY_Z) or pyxel.btnp(pyxel.KEY_RETURN):
                self.clear_page = 1
                return
        if pyxel.btnp(pyxel.KEY_R):
            self.reset()
            self.state = ST_PLAY
            self.start_bgm()

    def set_message(self, s, col=7):
        self.message = s
        self.message_col = col
        self.message_timer = 80

    def add_shake(self, amount):
        """画面を揺らす。強い揺れが来たときだけ向きを引き直す。
        頻度の高い出来事（通常ヒット・会心）からは呼ばないこと。"""
        if amount > self.shake:
            self.shake = amount
            self.shake_ang = random.uniform(0, math.tau)

    # ==========================================================================
    #  描画
    # ==========================================================================
    def draw(self):
        if self.state == ST_TITLE:
            self.draw_title()
            return
        if self.state == ST_CLEAR:
            self.draw_clear()
            return

        pyxel.cls(0)
        self.draw_field()
        self.draw_top_bar()
        self.draw_bottom_bar()
        if self.state == ST_SHOP:
            self.draw_shop()

    # --- 盤面 ---------------------------------------------------------------
    def draw_field(self):
        fl = FLOORS[self.floor_index]
        # 盤面の外に絵がはみ出さないよう切り取る。これでテロップと鉱石が重ならない。
        pyxel.clip(0, FIELD_TOP, SCREEN_W, FIELD_BOTTOM - FIELD_TOP)
        pyxel.rect(0, FIELD_TOP, SCREEN_W, FIELD_BOTTOM - FIELD_TOP, fl["bg"])

        if self.shake > 0.0:
            w = math.cos(pyxel.frame_count * SHAKE_SPEED) * self.shake
            pyxel.camera(int(math.cos(self.shake_ang) * w),
                         int(math.sin(self.shake_ang) * w))

        if HAS_SPRITES:
            # 階層ごとに岩の色を差し替えてから床を敷く
            for src, dst in fl["pal"].items():
                pyxel.pal(src, dst)
            for x, y, i in self.tiles:
                u, v = SPR_FLOOR[i]
                pyxel.blt(x, y, 0, u, v, 8, 8)
            for x, y, i in self.rubble:
                u, v = SPR_RUBBLE[i]
                pyxel.blt(x, y, 0, u, v, 8, 8, COLKEY)
            # 盤面のふちを岩壁で囲む
            wu, wv = SPR_WALL
            for x in range(0, SCREEN_W, 8):
                pyxel.blt(x, FIELD_TOP, 0, wu, wv, 8, 8)
                pyxel.blt(x, FIELD_BOTTOM - 8, 0, wu, wv, 8, 8)
            for y in range(FIELD_TOP, FIELD_BOTTOM, 8):
                pyxel.blt(0, y, 0, wu, wv, 8, 8)
                pyxel.blt(SCREEN_W - 8, y, 0, wu, wv, 8, 8)
            pyxel.pal()
        else:
            for x, y, c in self.bg_dots:
                pyxel.pset(x, y, c)

        if self.ladder:
            self.draw_ladder(*self.ladder)

        target = self.find_target()
        for o in sorted(self.ores, key=lambda o: o.y):
            o.draw(targeted=(o is target))
        if self.cat is not None:
            self.cat.draw()
        self.player.draw()
        for q in self.pests:
            q.draw()
        for p in self.particles:
            p.draw()
        for p in self.popups:
            p.draw()

        pyxel.camera()
        pyxel.clip()
        pyxel.line(0, FIELD_TOP - 1, SCREEN_W, FIELD_TOP - 1, 5)
        pyxel.line(0, FIELD_BOTTOM, SCREEN_W, FIELD_BOTTOM, 5)

    def draw_ladder(self, x, y):
        pyxel.rect(x - 8, y - 13, 16, 26, 0)
        if HAS_SPRITES:
            u, v = SPR_LADDER
            pyxel.blt(x - 8, y - 12, 0, u, v, 16, 24, COLKEY)
            if (pyxel.frame_count // 8) % 2 == 0:
                pyxel.rectb(x - 8, y - 13, 16, 26, 10)
        else:
            glow = 10 if (pyxel.frame_count // 8) % 2 == 0 else 9
            pyxel.rect(x - 6, y - 10, 2, 20, glow)
            pyxel.rect(x + 4, y - 10, 2, 20, glow)
            for i in range(5):
                pyxel.rect(x - 6, y - 9 + i * 4, 12, 1, glow)
        if math.hypot(self.player.x - x, self.player.y - y) <= 14:
            text_center_shadow(x, y - 24, "[X] 降りる", 11)

    # --- 上部の情報帯 -------------------------------------------------------
    def draw_top_bar(self):
        p = self.player
        fl = FLOORS[self.floor_index]
        pyxel.rect(0, 0, SCREEN_W, UI_TOP_H, 0)

        # 1段目: 階層名 / 状況 / 資源
        text(3, 2, fl["name"], 11)
        gold_s = f"お金 {fmt(p.gold)}"
        text_r(SCREEN_W - 3, 2, gold_s, 10)

        if self.floor_index == len(FLOORS) - 1:
            status, scol = "最深部", 8
        elif self.ladder is not None:
            status, scol = "ハシゴ発見", 11
        else:
            status, scol = "主: 未撃破", 8
        left_end = 3 + text_w(fl["name"])
        right_start = SCREEN_W - 3 - text_w(gold_s)
        if text_w(status) + 12 < right_start - left_end:
            text((left_end + right_start) // 2 - text_w(status) // 2, 2, status, scol)

        # 2段目: レベル+EXP / 攻撃力 / ピッケル
        lv_s = f"Lv.{p.level}"
        text(3, 16, lv_s, 7)
        bx = 6 + text_w(lv_s)
        pyxel.rect(bx, 20, 30, 4, 1)
        pyxel.rect(bx, 20, int(30 * (p.exp / p.exp_to_next)), 4, 11)
        text(bx + 36, 16, f"攻撃 {fmt(p.attack_damage(False))}", 7)
        pick = PICKAXES[p.pickaxe]
        text_r(SCREEN_W - 3, 16, pick["name"], pick["col"])

    # --- 下部のコマンド帯 ---------------------------------------------------
    def draw_bottom_bar(self):
        p = self.player
        pyxel.rect(0, UI_BOTTOM_Y + 1, SCREEN_W, SCREEN_H - UI_BOTTOM_Y, 0)

        ph = next((o for o in self.ores if o.phantom), None)
        if ph:
            self.draw_phantom_rows(ph)

        # メッセージがあるときはそちらを優先し、なければコンボやバフを出す
        if self.message_timer > 0:
            text_center(SCREEN_W // 2, ROW_INFO, self.message, self.message_col)
        else:
            left = []
            if p.combo >= 3:
                left.append(f"{p.combo}コンボ x{p.combo_mult:.2f}")
            if p.buff_active:
                left.append(f"怪しい薬 x{p.buff_mult} 残り{(p.buff_end - pyxel.frame_count) // FPS + 1}秒")
            if left:
                text(4, ROW_INFO, "   ".join(left), 10 if p.buff_active else 7)
            if p.potions > 0:
                text_r(SCREEN_W - 4, ROW_INFO, f"怪しい薬 x{p.potions}", 10)

        text(4, ROW_HINT, "[Z]ほる [S]みせ [C]くすり [X]はしご", 5)
        if TUNING:
            text_r(SCREEN_W - 4 - p.max_hp * 7 - 6, ROW_HINT,
                   f"[1-5]コウモリ:{PEST_PRESETS[PEST_LEVEL][0]}", 14)

        # 体力。階層を降りるたび全快するので、ここが尽きるのは「同じ階で3回やられた」とき。
        for i in range(p.max_hp):
            self.draw_heart(SCREEN_W - 4 - (p.max_hp - i) * 7, ROW_HINT + 2, i < p.hp)

    @staticmethod
    def draw_heart(x, y, filled):
        c = 8 if filled else 5
        pyxel.pset(x + 1, y, c)
        pyxel.pset(x + 3, y, c)
        pyxel.rect(x, y + 1, 5, 2, c)
        pyxel.rect(x + 1, y + 3, 3, 1, c)
        pyxel.pset(x + 2, y + 4, c)

    def draw_phantom_rows(self, ph):
        name = ph.name
        text(4, ROW_PH1, name, 8 if (pyxel.frame_count // 8) % 2 == 0 else 14)
        bx = 4 + text_w(name) + 6
        bw = SCREEN_W - bx - 52
        pyxel.rect(bx, ROW_PH1 + 4, bw, 5, 1)
        pyxel.rect(bx, ROW_PH1 + 4, max(0, int(bw * ph.hp_ratio)), 5, 8)
        text_r(SCREEN_W - 4, ROW_PH1, f"{ph.hp_ratio * 100:.1f}%", 7)

        # 残り時間は数字で出さない。消える直前だけ警告を点滅させ、あとは勘に任せる。
        if ph.remain_frames < PHANTOM_WARN_TIME and (pyxel.frame_count // 5) % 2 == 0:
            text_center(SCREEN_W // 2, ROW_PH2, "気配が薄れてきた…！", 8)

    # --- ショップ -----------------------------------------------------------
    def draw_shop(self):
        p = self.player
        items = self.shop_items()
        n = len(items)
        self.shop_cursor = max(0, min(self.shop_cursor, n - 1))

        x0, y0 = 10, 16
        w, h = SCREEN_W - 20, SCREEN_H - 34
        pyxel.rect(x0, y0, w, h, 0)
        pyxel.rectb(x0, y0, w, h, 7)
        pyxel.rect(x0 + 1, y0 + 1, w - 2, 15, 1)
        text(x0 + 5, y0 + 3, "坑道の魔女の館", 10)
        text_r(x0 + w - 5, y0 + 3, f"お金 {fmt(p.gold)}", 10)

        line = FLOORS[self.floor_index]["witch"]
        while text_w(line) > w - 10 and len(line) > 4:   # 長すぎる台詞は詰める
            line = line[:-2] + "…"
        text(x0 + 5, y0 + 18, line, 14)

        row_h = 26
        y = y0 + 34
        visible = items[self.shop_scroll:self.shop_scroll + self.SHOP_ROWS]
        list_top = y
        for i, it in enumerate(visible):
            idx = self.shop_scroll + i
            sel = (idx == self.shop_cursor)
            if sel:
                pyxel.rect(x0 + 2, y - 2, w - 4, row_h - 2, 1)
                text(x0 + 4, y, ">", 10)

            sold = it["price"] is None
            afford = (not sold) and p.gold >= it["price"]
            name_col = 5 if sold else (it["col"] if sel else 6)
            text(x0 + 14, y, it["label"], name_col)
            text(x0 + 14, y + 12, it["sub"], 5 if (sold or not sel) else 13)

            if sold:
                text_r(x0 + w - 6, y, "---", 5)
            else:
                text_r(x0 + w - 6, y, fmt(it["price"]), 10 if afford else 8)
            y += row_h

        # 画面外にまだ品物があることを、点滅する三角で知らせる
        blink = (pyxel.frame_count // 12) % 2 == 0
        ax = x0 + w // 2
        if self.shop_scroll > 0 and blink:
            pyxel.tri(ax, list_top - 8, ax - 4, list_top - 3, ax + 4, list_top - 3, 10)
        if self.shop_scroll + self.SHOP_ROWS < n and blink:
            by = list_top + self.SHOP_ROWS * row_h
            pyxel.tri(ax, by + 4, ax - 4, by - 1, ax + 4, by - 1, 10)

        # スクロールの位置を示す簡易バー
        if n > self.SHOP_ROWS:
            track_y, track_h = list_top, self.SHOP_ROWS * row_h
            bar_h = max(8, int(track_h * self.SHOP_ROWS / n))
            bar_y = track_y + int(track_h * self.shop_scroll / n)
            pyxel.rect(x0 + w - 3, track_y, 2, track_h, 1)
            pyxel.rect(x0 + w - 3, bar_y, 2, bar_h, 13)

        text_center(SCREEN_W // 2, y0 + h - 14, "[↑↓]えらぶ  [Z]かう  [S]とじる", 6)

    # --- タイトル -----------------------------------------------------------
    def draw_title(self):
        pyxel.cls(0)
        for i in range(60):
            pyxel.pset((i * 71 + pyxel.frame_count // 3) % SCREEN_W, (i * 37) % SCREEN_H, 1)

        text_big(SCREEN_W // 2, 40, "幻鉱", 10, scale=4)
        text_center(SCREEN_W // 2, 100, "- M A B O R O S H I -", 13)

        cx, cy = SCREEN_W // 2, 138
        col, dark = (8, 2) if (pyxel.frame_count // 14) % 2 == 0 else (14, 1)
        pyxel.circ(cx, cy, 16, dark)
        pyxel.circ(cx, cy, 15, col)
        rng = random.Random(99)
        for _ in range(16):
            a, d = rng.uniform(0, math.tau), rng.uniform(0, 10)
            pyxel.pset(cx + math.cos(a) * d, cy + math.sin(a) * d, dark)
        pyxel.pset(cx - 6, cy - 7, 7)
        pyxel.pset(cx - 5, cy - 7, 7)

        text_center(SCREEN_W // 2, 168, "最深部に眠る幻の鉱石で、", 6)
        text_center(SCREEN_W // 2, 182, "恋人に贈る指輪をつくりたい。", 6)

        if (pyxel.frame_count // 15) % 2 == 0:
            text_center(SCREEN_W // 2, 210, "[Z] ではじめる", 11)
        text_center(SCREEN_W // 2, 236, "矢印:移動 Z:採掘 S:みせ M:BGM", 5)

    # --- クリア -------------------------------------------------------------
    def draw_clear(self):
        if self.clear_page == 1:
            self.draw_true_end()
            return

        pyxel.cls(0)
        for i in range(80):
            a = i * 0.7 + pyxel.frame_count * 0.04
            d = (pyxel.frame_count * 1.6 + i * 13) % 200
            pyxel.pset(SCREEN_W // 2 + math.cos(a) * d, SCREEN_H // 2 + math.sin(a) * d,
                       10 if i % 3 else 11)

        p = self.player
        mark, title, is_true = self.rank
        col = 10 if (pyxel.frame_count // 8) % 2 == 0 else 7
        text_big(SCREEN_W // 2, 18, "幻の鉱石を", col, scale=2)
        text_big(SCREEN_W // 2, 46, "手に入れた", col, scale=2)
        text_center(SCREEN_W // 2, 74, "これで、あの指輪がつくれる。", 6)

        # 称号
        pyxel.rect(28, 84, SCREEN_W - 56, 30, 1)
        pyxel.rectb(28, 84, SCREEN_W - 56, 30, 10)
        text_big(56, 88, mark, 10, scale=2)
        text_center(SCREEN_W // 2 + 14, 94, title, 10)

        rows = [
            ("クリアタイム", mmss(self.play_frames)),
            ("最終レベル", f"Lv.{p.level}"),
            ("最終ピッケル", PICKAXES[p.pickaxe]["name"]),
            ("掘った鉱石", f"{p.total_mined} 個"),
        ]
        for i, (k, v) in enumerate(rows):
            y = 124 + i * 14
            text(34, y, k, 6)
            text(140, y, v, 7)

        if is_true:
            if (pyxel.frame_count // 15) % 2 == 0:
                text_center(SCREEN_W // 2, 190, "[Z] ……坑道の底から、音がする", 11)
        else:
            text_center(SCREEN_W // 2, 186, f"{TRUE_END_SEC // 60}分以内に幻を砕いたとき、", 13)
            text_center(SCREEN_W // 2, 200, "この坑道の本当の姿が見えるという。", 13)

        text_center(SCREEN_W // 2, 226, "[R] もう一度掘る", 6)

    def draw_true_end(self):
        pyxel.cls(0)
        # 下へ落ちていく光の粒
        for i in range(70):
            x = (i * 53 + 17) % SCREEN_W
            y = (i * 91 + pyxel.frame_count * 2) % SCREEN_H
            pyxel.pset(x, y, 1 if i % 3 else 5)

        text_center(SCREEN_W // 2, 22, "―― 真エンディング ――", 8)

        lines = [
            "指輪はできた。",
            "だが、砕けた岩の底に",
            "下へ続く穴があった。",
            "",
            "幻の鉱床は、坑道の終わりでは",
            "なかった。ずっと深くから伸びて",
            "きた何かの、いちばん浅いところ",
            "に過ぎなかった。",
            "",
            "坑道は、まだ続いている。",
        ]
        for i, s in enumerate(lines):
            if s:
                text(30, 54 + i * 15, s, 7 if i < 8 else 10)

        if (pyxel.frame_count // 15) % 2 == 0:
            text_center(SCREEN_W // 2, 226, "[R] もう一度掘る", 11)


if __name__ == "__main__":
    App()
