# ブラウザで遊ぶ版

リポジトリ直下の `index.html` は `maboroshi.py` と `maboroshi.pyxres` を丸ごと埋め込んだ
1ファイル完結の HTML。開けばブラウザで遊べる。

## 作り直しかた

ゲーム本体を変更したら、この手順で作り直す。

```sh
mkdir -p /tmp/build/maboroshi
cp maboroshi.py maboroshi.pyxres /tmp/build/maboroshi/
cd /tmp/build
pyxel package maboroshi maboroshi/maboroshi.py
pyxel app2html maboroshi.pyxapp
cp maboroshi.html <このリポジトリ>/index.html
```

リポジトリのフォルダをそのまま `pyxel package` に渡すと docs/ や .git まで
巻き込んで無駄に大きくなるので、必要な2ファイルだけを別の場所に置いて作る。

## 置き場所

GitHub Pages はブランチ直下か `/docs` しか公開フォルダに選べないため、
`index.html` はリポジトリの直下に置いてある。

## 注意

Pyxel 本体を `https://cdn.jsdelivr.net/gh/kitao/pyxel@2.9.8/wasm/pyxel.js`
から読み込むので、オフラインでは動かない。
