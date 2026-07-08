from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.models import AppSettings
from sem_archive.services.tag_service import TagService


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("環境設定")
        self.resize(640, 320)

        settings = db.get_settings()
        layout = QFormLayout(self)

        self.server_edit = QLineEdit(settings.server_root)
        self.local_edit = QLineEdit(settings.local_root)
        self.db_edit = QLineEdit(str(db.db_path))
        self.ext_edit = QLineEdit(settings.image_extensions)
        self.per_row = QSpinBox()
        self.per_row.setRange(1, 20)
        self.per_row.setValue(settings.images_per_row)

        layout.addRow("サーバールート", self._with_browse(self.server_edit, dir_mode=True))
        layout.addRow("ローカル保存先", self._with_browse(self.local_edit, dir_mode=True))
        layout.addRow("SQLite DB", self._with_browse(self.db_edit, dir_mode=False))
        layout.addRow("画像拡張子", self.ext_edit)
        layout.addRow("PPT 1行の画像数", self.per_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _with_browse(self, edit: QLineEdit, dir_mode: bool) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(edit)

        def browse() -> None:
            if dir_mode:
                path = QFileDialog.getExistingDirectory(self, "フォルダを選択", edit.text())
            else:
                path, _ = QFileDialog.getSaveFileName(
                    self, "DBファイル", edit.text(), "SQLite (*.db)"
                )
            if path:
                edit.setText(path)

        btn = QPushButton("参照")
        btn.clicked.connect(browse)
        h.addWidget(btn)
        return row

    def _save(self) -> None:
        settings = AppSettings(
            server_root=self.server_edit.text().strip(),
            local_root=self.local_edit.text().strip(),
            images_per_row=self.per_row.value(),
            image_extensions=self.ext_edit.text().strip(),
            export_page_mode=self.db.get_settings().export_page_mode,
            export_row_mode=self.db.get_settings().export_row_mode,
        )
        new_db = Path(self.db_edit.text().strip())
        if new_db and new_db != self.db.db_path:
            self.db.reopen(new_db)
        self.db.save_settings(settings)
        self.accept()


class TagEditorDialog(QDialog):
    def __init__(
        self,
        tag_service: TagService,
        target_type: str,
        target_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tag_service = tag_service
        self.target_type = target_type
        self.target_id = target_id
        self.setWindowTitle("タグ編集")
        self.resize(480, 420)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(QLabel("カテゴリ別タグ（複数選択可）"))
        layout.addWidget(self.list_widget)

        form = QHBoxLayout()
        self.cat_edit = QLineEdit()
        self.cat_edit.setPlaceholderText("新規カテゴリ名")
        add_cat = QPushButton("カテゴリ追加")
        add_cat.clicked.connect(self._add_category)
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText("新規タグ名")
        self.cat_for_tag = QLineEdit()
        self.cat_for_tag.setPlaceholderText("タグのカテゴリ名")
        add_tag = QPushButton("タグ追加")
        add_tag.clicked.connect(self._add_tag)
        form.addWidget(self.cat_edit)
        form.addWidget(add_cat)
        layout.addLayout(form)

        form2 = QHBoxLayout()
        form2.addWidget(self.cat_for_tag)
        form2.addWidget(self.tag_edit)
        form2.addWidget(add_tag)
        layout.addLayout(form2)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload()

    def _reload(self) -> None:
        self.list_widget.clear()
        selected = set(self.tag_service.repo.list_target_tag_ids(self.target_type, self.target_id))
        for tag in self.tag_service.tags():
            from PySide6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(f"[{tag.category_name}] {tag.name}")
            item.setData(Qt.UserRole, tag.id)
            self.list_widget.addItem(item)
            if tag.id in selected:
                item.setSelected(True)

    def _add_category(self) -> None:
        name = self.cat_edit.text().strip()
        if not name:
            return
        try:
            self.tag_service.add_category(name)
            self.cat_edit.clear()
            self._reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "エラー", str(exc))

    def _add_tag(self) -> None:
        cat_name = self.cat_for_tag.text().strip()
        tag_name = self.tag_edit.text().strip()
        if not cat_name or not tag_name:
            return
        cats = {c.name: c for c in self.tag_service.categories()}
        if cat_name not in cats:
            QMessageBox.warning(self, "エラー", f"カテゴリがありません: {cat_name}")
            return
        try:
            assert cats[cat_name].id is not None
            self.tag_service.add_tag(cats[cat_name].id, tag_name)
            self.tag_edit.clear()
            self._reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "エラー", str(exc))

    def _save(self) -> None:
        ids = [
            item.data(Qt.UserRole)
            for item in self.list_widget.selectedItems()
            if item.data(Qt.UserRole) is not None
        ]
        self.tag_service.set_tags_for(self.target_type, self.target_id, ids)
        self.accept()
