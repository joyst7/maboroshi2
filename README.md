# 幻鉱 -MABOROSHI- 2

まぼろし2 の開発フォルダ。前作 v5 を土台にする。

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
| `mining_game_v5.py` | ゲーム本体（土台）。`python3 mining_game_v5.py` で起動 |
| `build_assets.py` | スプライト生成。実行すると `maboroshi.pyxres` を書き出す |
| `maboroshi.pyxres` | スプライトリソース。`pyxel edit maboroshi.pyxres` で編集可 |
| `docs/` | 制作途中の説明用スクショ（本編とは無関係） |

## 動かす

```sh
pip install pyxel
python3 mining_game_v5.py
```

## アセットを作り直す

```sh
python3 build_assets.py       # maboroshi.pyxres を再生成
pyxel edit maboroshi.pyxres   # 手で描き直す
```

## 配布ビルド

```sh
pyxel package . mining_game_v5.py   # maboroshi.pyxapp
pyxel app2html maboroshi.pyxapp     # maboroshi.html
```
