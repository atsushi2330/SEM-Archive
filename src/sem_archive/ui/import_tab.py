from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.services.copy_service import CopyService
from sem_archive.utils.paths import normalize_request_nos


class ImportTab(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.repo = Repository(db.connection)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SEM依頼番号（カンマ / 改行区切り、または下のリストへ追加）"))

        self.bulk_edit = QTextEdit()
        self.bulk_edit.setPlaceholderText("例:\n202607080211\n202607080212, 202607080213")
        self.bulk_edit.setFixedHeight(100)
        layout.addWidget(self.bulk_edit)

        row = QHBoxLayout()
        self.single_edit = QLineEdit()
        self.single_edit.setPlaceholderText("1件追加")
        add_btn = QPushButton("リストに追加")
        add_btn.clicked.connect(self._add_one)
        apply_bulk = QPushButton("一括をリストへ反映")
        apply_bulk.clicked.connect(self._apply_bulk)
        clear_btn = QPushButton("リストクリア")
        clear_btn.clicked.connect(lambda: self.list_widget.clear())
        row.addWidget(self.single_edit)
        row.addWidget(add_btn)
        row.addWidget(apply_bulk)
        row.addWidget(clear_btn)
        layout.addLayout(row)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        layout.addWidget(QLabel("Lot番号（カンマ区切り・複数可）"))
        self.lot_edit = QLineEdit()
        layout.addWidget(self.lot_edit)

        layout.addWidget(QLabel("条件（SEM全体）"))
        self.condition_edit = QLineEdit()
        layout.addWidget(self.condition_edit)

        layout.addWidget(QLabel("メモ（SEM全体）"))
        self.memo_edit = QTextEdit()
        self.memo_edit.setFixedHeight(70)
        layout.addWidget(self.memo_edit)

        run_btn = QPushButton("サーバーからコピーして取込")
        run_btn.clicked.connect(self._run_import)
        layout.addWidget(run_btn)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

    def _current_nos(self) -> list[str]:
        nos = []
        for i in range(self.list_widget.count()):
            nos.append(self.list_widget.item(i).text())
        return nos

    def _add_one(self) -> None:
        value = self.single_edit.text().strip()
        if not value:
            return
        existing = set(self._current_nos())
        if value not in existing:
            self.list_widget.addItem(QListWidgetItem(value))
        self.single_edit.clear()

    def _apply_bulk(self) -> None:
        nos = normalize_request_nos(self.bulk_edit.toPlainText())
        existing = set(self._current_nos())
        for no in nos:
            if no not in existing:
                self.list_widget.addItem(QListWidgetItem(no))
                existing.add(no)

    def _run_import(self) -> None:
        nos = self._current_nos()
        if not nos:
            self._apply_bulk()
            nos = self._current_nos()
        if not nos:
            QMessageBox.warning(self, "入力不足", "SEM依頼番号を指定してください")
            return
        settings = self.db.get_settings()
        if not settings.server_root or not settings.local_root:
            QMessageBox.warning(self, "設定不足", "環境設定でサーバー/ローカルパスを設定してください")
            return
        lots = [x.strip() for x in self.lot_edit.text().split(",") if x.strip()]
        service = CopyService(self.repo, settings)
        results = service.import_cases(
            nos,
            lot_nos=lots,
            memo=self.memo_edit.toPlainText().strip(),
            condition=self.condition_edit.text().strip(),
        )
        lines = []
        for r in results:
            mark = "OK" if r.success else "NG"
            lines.append(f"[{mark}] {r.request_no}: {r.message}")
        self.log.setPlainText("\n".join(lines))
