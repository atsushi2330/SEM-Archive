from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.models import SearchFilters, SemCase
from sem_archive.services.tag_service import TagService
from sem_archive.ui.dialogs import TagEditorDialog
from sem_archive.utils.image_io import load_thumbnail
from sem_archive.utils.paths import open_in_explorer


class BrowseTab(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.repo = Repository(db.connection)
        self.tag_service = TagService(self.repo)
        self.current_sem: SemCase | None = None
        self.current_folder_id: int | None = None

        root = QHBoxLayout(self)
        splitter = QSplitter()
        root.addWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        search_box = QGroupBox("検索")
        search_form = QFormLayout(search_box)
        self.query_edit = QLineEdit()
        self.lot_edit = QLineEdit()
        self.slot_edit = QLineEdit()
        self.tag_filter = QListWidget()
        self.tag_filter.setSelectionMode(QListWidget.MultiSelection)
        self.tag_filter.setMaximumHeight(100)
        search_form.addRow("キーワード", self.query_edit)
        search_form.addRow("Lot", self.lot_edit)
        search_form.addRow("Slot", self.slot_edit)
        search_form.addRow("タグ", self.tag_filter)
        search_btn = QPushButton("検索")
        search_btn.clicked.connect(self.refresh_case_list)
        search_form.addRow(search_btn)
        left_layout.addWidget(search_box)

        left_layout.addWidget(QLabel("SEM依頼"))
        self.case_list = QListWidget()
        self.case_list.currentItemChanged.connect(self._on_case_selected)
        left_layout.addWidget(self.case_list)

        left_layout.addWidget(QLabel("フォルダツリー"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["フォルダ", "Slot", "メモ"])
        self.tree.itemSelectionChanged.connect(self._on_folder_selected)
        left_layout.addWidget(self.tree)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        meta = QGroupBox("メタデータ")
        meta_form = QFormLayout(meta)
        self.meta_title = QLabel("-")
        self.condition_edit = QLineEdit()
        self.memo_edit = QTextEdit()
        self.memo_edit.setFixedHeight(60)
        self.slot_id_edit = QLineEdit()
        self.lots_label = QLabel("-")
        meta_form.addRow("対象", self.meta_title)
        meta_form.addRow("Lot", self.lots_label)
        meta_form.addRow("条件", self.condition_edit)
        meta_form.addRow("メモ", self.memo_edit)
        meta_form.addRow("Slot ID", self.slot_id_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("メタ保存")
        save_btn.clicked.connect(self._save_meta)
        tag_btn = QPushButton("タグ編集")
        tag_btn.clicked.connect(self._edit_tags)
        explorer_btn = QPushButton("エクスプローラーで開く")
        explorer_btn.clicked.connect(self._open_explorer)
        refresh_btn = QPushButton("再読込")
        refresh_btn.clicked.connect(self.refresh_case_list)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(tag_btn)
        btn_row.addWidget(explorer_btn)
        btn_row.addWidget(refresh_btn)
        meta_form.addRow(btn_row)
        right_layout.addWidget(meta)

        right_layout.addWidget(QLabel("画像プレビュー"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.thumb_host = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_host)
        self.scroll.setWidget(self.thumb_host)
        right_layout.addWidget(self.scroll)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.refresh_case_list()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._reload_tag_filter()

    def _reload_tag_filter(self) -> None:
        selected_ids = {
            item.data(Qt.UserRole)
            for item in self.tag_filter.selectedItems()
            if item.data(Qt.UserRole) is not None
        }
        self.tag_filter.clear()
        for tag in self.tag_service.tags():
            item = QListWidgetItem(f"[{tag.category_name}] {tag.name}")
            item.setData(Qt.UserRole, tag.id)
            self.tag_filter.addItem(item)
            if tag.id in selected_ids:
                item.setSelected(True)

    def refresh_case_list(self) -> None:
        self._reload_tag_filter()
        tag_ids = [
            item.data(Qt.UserRole)
            for item in self.tag_filter.selectedItems()
            if item.data(Qt.UserRole) is not None
        ]
        filters = SearchFilters(
            query=self.query_edit.text(),
            lot_no=self.lot_edit.text(),
            slot_id=self.slot_edit.text(),
            tag_ids=tag_ids,
        )
        cases = self.repo.search_sem_cases(filters)
        self.case_list.clear()
        for case in cases:
            item = QListWidgetItem(f"{case.request_no}")
            item.setData(Qt.UserRole, case.id)
            self.case_list.addItem(item)
        self.tree.clear()
        self._clear_thumbs()

    def _on_case_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            self.current_sem = None
            return
        sem_id = current.data(Qt.UserRole)
        self.current_sem = self.repo.get_sem(sem_id)
        self.current_folder_id = None
        self._load_tree()
        self._show_sem_meta()
        self._show_images(Path(self.current_sem.local_path) if self.current_sem else None)

    def _load_tree(self) -> None:
        self.tree.clear()
        if not self.current_sem or self.current_sem.id is None:
            return
        folders = self.repo.list_folders(self.current_sem.id)
        items: dict[str, QTreeWidgetItem] = {}
        root_item = QTreeWidgetItem([self.current_sem.request_no, "", self.current_sem.memo[:40]])
        root_item.setData(0, Qt.UserRole, {"type": "sem", "id": self.current_sem.id})
        self.tree.addTopLevelItem(root_item)

        for folder in folders:
            node = QTreeWidgetItem(
                [
                    folder.folder_name,
                    folder.slot_id or "",
                    (folder.memo or "")[:40],
                ]
            )
            node.setData(0, Qt.UserRole, {"type": "folder", "id": folder.id})
            items[folder.relative_path] = node
            if "/" in folder.relative_path:
                parent_rel = folder.relative_path.rsplit("/", 1)[0]
                parent = items.get(parent_rel, root_item)
                parent.addChild(node)
            else:
                root_item.addChild(node)
        self.tree.expandToDepth(1)

    def _on_folder_selected(self) -> None:
        items = self.tree.selectedItems()
        if not items or not self.current_sem:
            return
        data = items[0].data(0, Qt.UserRole) or {}
        if data.get("type") == "sem":
            self.current_folder_id = None
            self._show_sem_meta()
            self._show_images(Path(self.current_sem.local_path))
            return
        folder_id = data.get("id")
        self.current_folder_id = folder_id
        folder = self.repo.get_folder(folder_id)
        if not folder:
            return
        self.meta_title.setText(f"{self.current_sem.request_no} / {folder.relative_path}")
        self.condition_edit.setText(folder.condition)
        self.memo_edit.setPlainText(folder.memo)
        self.slot_id_edit.setText(folder.slot_id or "")
        self.slot_id_edit.setEnabled(True)
        lots = self.repo.list_lots(self.current_sem.id) if self.current_sem.id else []
        self.lots_label.setText(", ".join(l.lot_no for l in lots) or "-")
        path = Path(self.current_sem.local_path) / folder.relative_path
        self._show_images(path)

    def _show_sem_meta(self) -> None:
        if not self.current_sem:
            return
        self.meta_title.setText(self.current_sem.request_no)
        self.condition_edit.setText(self.current_sem.condition)
        self.memo_edit.setPlainText(self.current_sem.memo)
        self.slot_id_edit.setText("")
        self.slot_id_edit.setEnabled(False)
        lots = self.repo.list_lots(self.current_sem.id) if self.current_sem.id else []
        self.lots_label.setText(", ".join(l.lot_no for l in lots) or "-")

    def _save_meta(self) -> None:
        if not self.current_sem or self.current_sem.id is None:
            return
        if self.current_folder_id is None:
            self.repo.update_sem_meta(
                self.current_sem.id,
                self.memo_edit.toPlainText().strip(),
                self.condition_edit.text().strip(),
            )
            self.current_sem = self.repo.get_sem(self.current_sem.id)
        else:
            slot = self.slot_id_edit.text().strip()
            self.repo.update_folder_meta(
                self.current_folder_id,
                memo=self.memo_edit.toPlainText().strip(),
                condition=self.condition_edit.text().strip(),
                slot_id=slot or None,
                is_slot=bool(slot),
            )
        self._load_tree()
        QMessageBox.information(self, "保存", "メタデータを保存しました")

    def _edit_tags(self) -> None:
        if not self.current_sem or self.current_sem.id is None:
            return
        if self.current_folder_id is None:
            dlg = TagEditorDialog(self.tag_service, "sem", self.current_sem.id, self)
        else:
            dlg = TagEditorDialog(self.tag_service, "folder", self.current_folder_id, self)
        dlg.exec()
        self._reload_tag_filter()

    def _open_explorer(self) -> None:
        if not self.current_sem:
            return
        path = Path(self.current_sem.local_path)
        if self.current_folder_id is not None:
            folder = self.repo.get_folder(self.current_folder_id)
            if folder:
                path = path / folder.relative_path
        open_in_explorer(path)

    def _clear_thumbs(self) -> None:
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _show_images(self, folder: Path | None) -> None:
        self._clear_thumbs()
        if folder is None or not folder.exists():
            return
        settings = self.db.get_settings()
        exts = settings.extension_set()
        files = [
            p
            for p in sorted(folder.iterdir())
            if p.is_file() and p.suffix.lower() in exts
        ]
        # 直下に無く深い場合は1階層だけ追加表示
        if not files:
            files = [
                p
                for p in sorted(folder.rglob("*"))
                if p.is_file() and p.suffix.lower() in exts
            ][:200]
        cols = 4
        for idx, path in enumerate(files[:120]):
            thumb = load_thumbnail(path)
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            if thumb is not None:
                data = thumb.tobytes("raw", "RGB")
                qimg = QImage(data, thumb.width, thumb.height, thumb.width * 3, QImage.Format_RGB888)
                pix = QPixmap.fromImage(qimg.copy())
                label.setPixmap(pix)
            else:
                label.setText("(読込失敗)")
            caption = QLabel(path.name)
            caption.setWordWrap(True)
            cell = QWidget()
            v = QVBoxLayout(cell)
            v.addWidget(label)
            v.addWidget(caption)
            self.thumb_grid.addWidget(cell, idx // cols, idx % cols)
