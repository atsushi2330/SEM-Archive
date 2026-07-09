from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.services.copy_service import CopyService
from sem_archive.services.metadata_export import write_sem_info_file
from sem_archive.ui.dialogs import ServerFolderPickerDialog
from sem_archive.ui.folder_columns import COL_PATH, FIELD_BY_COL, HEADERS
from sem_archive.utils.paths import normalize_request_nos


class ImportTab(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.repo = Repository(db.connection)
        self._loading_recent = False
        self._recent_sem_ids: list[int] = []

        layout = QVBoxLayout(self)

        # サーバーパス（環境設定から移動）
        server_box = QGroupBox("サーバーSEMフォルダ")
        server_row = QHBoxLayout(server_box)
        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText(r"例: \\server\share\SEM")
        settings = db.get_settings()
        self.server_edit.setText(settings.server_root)
        browse_btn = QPushButton("参照")
        browse_btn.clicked.connect(self._browse_server)
        server_row.addWidget(self.server_edit, 1)
        server_row.addWidget(browse_btn)
        layout.addWidget(server_box)

        layout.addWidget(QLabel("SEM依頼番号（カンマ / 改行区切り、またはリストから選択）"))

        self.bulk_edit = QTextEdit()
        self.bulk_edit.setPlaceholderText("例:\n202607080211\n202607080212, 202607080213")
        self.bulk_edit.setFixedHeight(80)
        layout.addWidget(self.bulk_edit)

        row = QHBoxLayout()
        apply_bulk = QPushButton("一括をリストへ反映")
        apply_bulk.clicked.connect(self._apply_bulk)
        pick_btn = QPushButton("リストから選ぶ")
        pick_btn.clicked.connect(self._pick_from_server)
        clear_btn = QPushButton("リストクリア")
        clear_btn.clicked.connect(lambda: self.list_widget.clear())
        remove_btn = QPushButton("リストから削除")
        remove_btn.clicked.connect(self._remove_from_list)
        row.addWidget(apply_bulk)
        row.addWidget(pick_btn)
        row.addWidget(remove_btn)
        row.addWidget(clear_btn)
        layout.addLayout(row)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.list_widget)

        run_btn = QPushButton("サーバーからコピーして取込")
        run_btn.clicked.connect(self._run_import)
        layout.addWidget(run_btn)

        recent_box = QGroupBox("取込直後のメタデータ編集（閲覧タブと同じ項目・編集すると説明ファイルも更新）")
        recent_layout = QVBoxLayout(recent_box)
        self.recent_table = QTableWidget(0, len(HEADERS))
        self.recent_table.setHorizontalHeaderLabels(HEADERS)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recent_table.horizontalHeader().setSectionResizeMode(COL_PATH, QHeaderView.Stretch)
        self.recent_table.itemChanged.connect(self._on_recent_changed)
        recent_layout.addWidget(self.recent_table)
        layout.addWidget(recent_box, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        layout.addWidget(self.log)

    def _browse_server(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        start = self.server_edit.text().strip()
        path = QFileDialog.getExistingDirectory(self, "サーバーSEMフォルダを選択", start)
        if path:
            self.server_edit.setText(path)
            self._persist_server_root(path)

    def _persist_server_root(self, path: str) -> None:
        settings = self.db.get_settings()
        settings.server_root = path.strip()
        self.db.save_settings(settings)

    def _current_nos(self) -> list[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def _add_to_list(self, nos: list[str]) -> None:
        existing = set(self._current_nos())
        for no in nos:
            if no and no not in existing:
                self.list_widget.addItem(QListWidgetItem(no))
                existing.add(no)

    def _apply_bulk(self) -> None:
        self._add_to_list(normalize_request_nos(self.bulk_edit.toPlainText()))

    def _remove_from_list(self) -> None:
        selected = self.list_widget.selectedItems()
        if not selected:
            QMessageBox.information(self, "削除", "リストから削除する番号を選択してください")
            return
        removed = [item.text() for item in selected]
        for row in sorted({self.list_widget.row(item) for item in selected}, reverse=True):
            self.list_widget.takeItem(row)
        self.log.append(f"リストから削除（未取込の候補のみ）: {', '.join(removed)}")

    def _pick_from_server(self) -> None:
        server = self.server_edit.text().strip()
        if not server:
            QMessageBox.warning(self, "未設定", "サーバーSEMフォルダのパスを入力してください")
            return
        self._persist_server_root(server)
        try:
            dlg = ServerFolderPickerDialog(server, set(self._current_nos()), self)
            if dlg.exec():
                picked = dlg.selected_folders()
                self._add_to_list(picked)
                if picked:
                    self.log.append(f"リストに追加: {', '.join(picked)}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "エラー", f"フォルダ一覧を開けませんでした:\n{exc}")

    def _run_import(self) -> None:
        nos = self._current_nos()
        if not nos:
            self._apply_bulk()
            nos = self._current_nos()
        if not nos:
            QMessageBox.warning(self, "入力不足", "SEM依頼番号を指定してください")
            return

        server = self.server_edit.text().strip()
        if not server:
            QMessageBox.warning(self, "未設定", "サーバーSEMフォルダのパスを入力してください")
            return
        self._persist_server_root(server)

        settings = self.db.get_settings()
        settings.server_root = server
        if not settings.local_root:
            QMessageBox.warning(self, "設定不足", "環境設定でローカル保存先を設定してください")
            return
        self.db.save_settings(settings)

        service = CopyService(self.repo, settings)
        results = service.import_cases(nos)
        lines = []
        imported_ids: list[int] = []
        for r in results:
            mark = "OK" if r.success else "NG"
            lines.append(f"[{mark}] {r.request_no}: {r.message}")
            if r.success and r.sem_case_id is not None:
                imported_ids.append(r.sem_case_id)
        self.log.setPlainText("\n".join(lines))

        if imported_ids:
            for sem_id in imported_ids:
                if sem_id not in self._recent_sem_ids:
                    self._recent_sem_ids.append(sem_id)
            self._reload_recent_table()
            self.data_changed.emit()

    def _reload_recent_table(self) -> None:
        self._loading_recent = True
        self.recent_table.setRowCount(0)
        if not self._recent_sem_ids:
            self._loading_recent = False
            return

        id_set = set(self._recent_sem_ids)
        for sem, folder in self.repo.list_all_folders():
            if sem.id not in id_set or folder.id is None:
                continue
            display = f"{sem.request_no} - {folder.relative_path.replace('/', ' - ')}"
            row = self.recent_table.rowCount()
            self.recent_table.insertRow(row)
            values = [
                display,
                folder.substrate,
                folder.lot_name,
                folder.lot_id,
                folder.slot_id or "",
                folder.process,
                folder.condition,
                folder.memo,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(
                    Qt.UserRole,
                    {
                        "folder_id": folder.id,
                        "sem_id": sem.id,
                        "relative_path": folder.relative_path,
                    },
                )
                if col == COL_PATH:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.recent_table.setItem(row, col, item)
        self._loading_recent = False

    def _on_recent_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_recent:
            return
        col = item.column()
        field = FIELD_BY_COL.get(col)
        if not field:
            return
        data = item.data(Qt.UserRole) or {}
        folder_id = data.get("folder_id")
        sem_id = data.get("sem_id")
        if folder_id is None:
            path_item = self.recent_table.item(item.row(), COL_PATH)
            data = (path_item.data(Qt.UserRole) if path_item else {}) or {}
            folder_id = data.get("folder_id")
            sem_id = data.get("sem_id")
        if folder_id is None:
            return
        try:
            self.repo.update_folder_field(int(folder_id), field, item.text())
            if sem_id is not None:
                write_sem_info_file(self.repo, int(sem_id))
            self.data_changed.emit()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "保存エラー", str(exc))
