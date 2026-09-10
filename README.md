# 幻鉱 -MABOROSHI- 2

採掘クリッカー。前作 v5 をもとに、B6F〜B10F のボーナスステージとやりこみ要素を足した完成版。

## ブラウザで遊ぶ

https://joyst7.github.io/maboroshi2/

`index.html` はゲーム本体とリソースを埋め込んだ1ファイル完結のビルド。
作り直しかたは [docs/web-build.md](docs/web-build.md) を参照。

## 操作

| キー | |
|---|---|
| 矢印 | 移動 |
| Z | 採掘 |
| X | ハシゴを降りる |
| S | みせ |
| C | 怪しい薬を飲む |
| M | BGM の切り替え |
| R | もう一度（クリア後） |

キーボードで遊ぶ前提。

## ファイル

| ファイル | 役割 |
|---|---|
| `maboroshi.py` | ゲーム本体。`python3 maboroshi.py` で起動 |
| `build_assets.py` | スプライト生成。実行すると `maboroshi_seed.pyxres` を書き出す（種。本物は下記） |
| `maboroshi.pyxres` | スプライトリソース。`pyxel edit maboroshi.pyxres` で編集可 |
| `docs/design_v2.md` | 設計メモ。やりたいこと整理から数値バランスの検証まで |
| `docs/web-build.md` | ブラウザ版の作り直しかた |

## 動かす

```sh
pip install pyxel
python3 maboroshi.py
```

## アセットを作り直す

```sh
python3 build_assets.py       # maboroshi_seed.pyxres を再生成（種）
pyxel edit maboroshi.pyxres   # 本物を手で描き直す
```

## 配布ビルド

```sh
pyxel package . maboroshi.py   # maboroshi.pyxapp
pyxel app2html maboroshi.pyxapp   # maboroshi.html
```
