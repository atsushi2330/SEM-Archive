from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

TUTORIAL_HTML = """
<h2>SEM-Archive チュートリアル</h2>
<p>社内サーバーの SEM 画像をローカルに取り込み、整理・閲覧・PowerPoint 抽出まで行うツールです。</p>

<h3>1. 最初に（環境設定）</h3>
<ol>
<li>メニュー <b>環境設定</b> を開く</li>
<li><b>ローカル保存先</b> … 取り込んだ SEM フォルダの保存先</li>
<li><b>テーマカラー</b> … 画面の色合い（お好みで）</li>
<li><b>画像拡張子</b> / <b>PPT 1行の画像数</b> … 必要に応じて変更</li>
</ol>

<h3>2. 取込タブ</h3>
<ol>
<li><b>サーバーSEMフォルダ</b> に UNC パス（例: <code>\\\\server\\share\\SEM</code>）を入力</li>
<li>SEM依頼番号を入力するか、<b>リストから選ぶ</b> でサーバー上のフォルダをチェック選択</li>
<li><b>サーバーからコピーして取込</b> でローカルへコピー</li>
<li>取込直後の表で Lot / Slot / 条件 / メモ を編集可能（<code>SEM番号_説明.txt</code> も更新）</li>
</ol>

<h3>3. 閲覧タブ</h3>
<ul>
<li>キーワード検索・タグ絞り込み・列ヘッダーの <b>▼</b> で Excel 風フィルタ</li>
<li>表のセルを直接編集すると DB と説明ファイルが更新されます</li>
<li><b>画像プレビュー</b>
  <ul>
    <li><b>「パス」列（SEM番号）をクリック</b> … 1枚のときは表示・別番号への切替（Ctrl不要）</li>
    <li><b>Ctrl + クリック</b> … 2枚以上の分割表示を追加（最大4つ）</li>
    <li>プレビュー内で <b>Ctrl + マウスホイール</b> … サムネサイズ変更</li>
    <li>サムネをクリック … 既定アプリで画像を開く</li>
    <li><b>閉じる</b> ボタン … そのプレビューだけ閉じる</li>
    <li><b>プレビュー全閉じ</b> … まとめて閉じる</li>
  </ul>
</li>
<li><b>エクスプローラーで開く</b> … 選択行のフォルダを開く</li>
<li><b>タグ編集</b> … 選択行のフォルダ（または SEM）にタグ付け</li>
</ul>

<h3>4. 抽出タブ</h3>
<ol>
<li>SEM / フォルダにチェックを入れる</li>
<li>ページ分け（Slot単位 / フラット）・行分け（サブフォルダ / なし）を選ぶ</li>
<li><b>PowerPointへ出力</b> → 完了後 <b>PowerPointを開く</b> も可能</li>
</ol>

<h3>想定フォルダ構造</h3>
<pre>
\\\\server\\...\\
  202607080211\\      ← SEM依頼番号
    S1\\
      C\\
      M\\
      E\\
</pre>

<h3>ショートカットまとめ</h3>
<table cellpadding="4">
<tr><td><b>パス列クリック</b></td><td>プレビュー表示・切替（1枚のとき）</td></tr>
<tr><td><b>Ctrl + パス列クリック</b></td><td>プレビュー追加（2枚以上のとき）</td></tr>
<tr><td><b>Ctrl + ホイール</b></td><td>サムネズーム（プレビュー内）</td></tr>
</table>
"""


class TutorialDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("チュートリアル")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(TUTORIAL_HTML)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_btn = buttons.button(QDialogButtonBox.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(buttons)
