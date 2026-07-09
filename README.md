# SEM-Archive

Windows向け **SEM画像アーカイブ / 閲覧 / PowerPoint抽出** ツールです。

社内サーバー上の SEM依頼番号フォルダをローカルへ取り込み、Lot / Slot / 条件 / メモ / タグで整理し、選択した配下画像を劣化なく PowerPoint（`.pptx`）へ並べます。

## 主な機能

### 取込
- 環境設定で **サーバールート** と **ローカル保存先** を指定
- SEM依頼番号を複数入力（カンマ / 改行、またはリストから選択）
- サーバーからフォルダごとコピー
- Lot番号（複数）・条件・メモを SEM に紐づけ
- Slotフォルダ（`s1` / `S1` / `slot1` など）を自動推定
- 下位フォルダ単位でも条件・メモを編集可能

### 閲覧
- SEM番号 / 条件 / メモ / Lot / Slot / タグで検索
- 階層フォルダツリー + サムネイル表示
- エクスプローラーで開く
- タグはカテゴリ付き（初期: `下地` / `工程` / `評価内容`、追加可）
- SEM単位・フォルダ単位の両方にタグ付け可能

### 抽出（PowerPoint）
- SEM / フォルダにチェックして配下画像を出力
- **ページ分け**: Slot単位 / フラット
- **行分け**: サブフォルダ（例: C/M/E） / なし
- 1行の画像数デフォルト 10（設定変更可）
- ラベルは画像下。パスは SEM依頼番号より下から（例: `S1/C/img001.jpg`）
- JPG/PNG は再エンコードせず埋め込み、TIFF はロスレス PNG 化
- Alt text に 条件 / LotID / SlotID / フォルダ名 / ファイル名 を埋込

## 想定フォルダ構造

```text
\\server\...\
  202607080211\      # SEM依頼番号
    S1\
      C\
      M\
      E\
    S2\
```

## 必要環境

- Windows 10/11
- Python 3.11+（ソース実行時）
- または GitHub Releases の `.exe`（Python不要）

## セットアップ（開発者）

```powershell
git clone https://github.com/atsushi2330/SEM-Archive.git
cd SEM-Archive
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
sem-archive
```

または:

```powershell
python -m sem_archive.app
```

## 使い方（ざっくり）

1. メニュー **環境設定** でローカル保存先 / DB場所を設定
2. **取込** タブでサーバーSEMフォルダを指定し、SEM依頼番号を入れてコピー（「リストから選ぶ」でサーバー上のフォルダを選択可）
3. **閲覧** タブで検索・メモ/タグ編集
4. **抽出** タブでチェックして `.pptx` 出力

取込後は SEM依頼フォルダ内に `SEM番号_説明.txt`（例: `202607080211_説明.txt`）が生成され、Lot/条件などをソフトなしでも確認できます。

## exe ビルド / 配布

### ローカル

```powershell
.\scripts\build_windows.ps1
```

成果物:
- フォルダ: `dist\SEM-Archive\`（**このフォルダごと**配布）
- ZIP: `SEM-Archive-windows.zip`（スクリプトが自動作成）

**重要**: `SEM-Archive.exe` だけコピーしないこと。同フォルダ内の `_internal` なども必須です。

### 起動先PCで「Failed to load Python DLL」と出るとき

1. **フォルダ丸ごと**展開しているか確認（exe単体NG）
2. 起動先PCに [Visual C++ 再頒布可能パッケージ (x64)](https://learn.microsoft.com/ja-jp/cpp/windows/latest-supported-vc-redist) をインストール
3. ビルドは **Python 3.12 (64bit)** 推奨。WinPython でビルドした場合は最新の `build_windows.ps1` を使う（`python312.dll` を同梱）
4. 再ビルド後、`dist\SEM-Archive\_internal\python312.dll`（または `python3.dll`）があるか確認

### GitHub Actions

1. Actions の **Build Windows EXE** を `workflow_dispatch` で実行、または Release を publish
2. 生成された `SEM-Archive-windows.zip` を Releases に添付（Release publish 時は自動添付）

Python がない PC では zip を展開して `SEM-Archive.exe` を起動してください。

## テスト

```powershell
pytest -q
```

## ライセンス

MIT

## 再起動前処理
import sys
from PySide6.QtWidgets import QApplication
app = QApplication.instance()
if app:
    app.quit()

## 2回目起動用コード
import sys
import os

base = r"C:\Users\あなたのパス\SEM-Archive-main"
sys.path.insert(0, os.path.join(base, "src"))

from PySide6.QtWidgets import QApplication
from sem_archive.app import main

# 既にQApplicationがあれば作らない
if QApplication.instance() is None:
    main()
else:
    print("すでに起動済み。カーネルを再起動してからもう一度実行してね")

## ビルド
import sys, os, subprocess
print(sys.executable)  # どのPythonか確認
base = r"C:\Users\あなたのパス\SEM-Archive-main"
os.chdir(base)
subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--windowed",
    "--name", "SEM-Archive",
    "--paths", "src",
    "--collect-all", "PySide6",
    "--collect-all", "pptx",
    "src/sem_archive/app.py",
], check=True)
print("できた:", os.path.abspath("dist/SEM-Archive/SEM-Archive.exe"))

