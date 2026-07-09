from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.models import FolderRecord, SearchFilters, SemCase
from sem_archive.services.metadata_export import write_sem_info_file
from sem_archive.services.tag_service import TagService
from sem_archive.ui.dialogs import TagEditorDialog
from sem_archive.utils.image_io import load_thumbnail
from sem_archive.utils.paths import open_in_explorer, open_with_default_app

from sem_archive.ui.folder_columns import COL_PATH, FIELD_BY_COL, HEADERS

MAX_PREVIEW_PANES = 4
EMPTY_VALUE_LABEL = "(空白)"


class ColumnFilterPopup(QFrame):
    """Excel風: カラム値のチェックリストで行を出し分け。"""

    applied = Signal(int, object)  # col, set[str] | None  (None = フィルタなし)
    sort_requested = Signal(int, int)  # col, order (Qt.AscendingOrder / DescendingOrder)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("filterPopup")
        self.setFrameShape(QFrame.StyledPanel)
        self._column = 0
        self._all_values: list[str] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        sort_row = QHBoxLayout()
        asc_btn = QPushButton("昇順で並べ替え")
        asc_btn.clicked.connect(lambda: self._request_sort(Qt.AscendingOrder))
        desc_btn = QPushButton("降順で並べ替え")
        desc_btn.clicked.connect(lambda: self._request_sort(Qt.DescendingOrder))
        sort_row.addWidget(asc_btn)
        sort_row.addWidget(desc_btn)
        layout.addLayout(sort_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("リスト内検索…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_list)
        layout.addWidget(self.search)

        btn_row = QHBoxLayout()
        all_btn = QPushButton("すべて選択")
        all_btn.clicked.connect(self._check_all)
        none_btn = QPushButton("すべて解除")
        none_btn.clicked.connect(self._uncheck_all)
        btn_row.addWidget(all_btn)
        btn_row.addWidget(none_btn)
        layout.addLayout(btn_row)

        self.list = QListWidget()
        self.list.setMinimumWidth(260)
        self.list.setMaximumHeight(320)
        layout.addWidget(self.list)

        ok_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("キャンセル")
        cancel_btn.clicked.connect(self.close)
        ok_row.addWidget(ok_btn)
        ok_row.addWidget(cancel_btn)
        layout.addLayout(ok_row)

    def open_for(
        self,
        column: int,
        values: list[str],
        selected: set[str] | None,
        global_pos,
    ) -> None:
        self._column = column
        unique = sorted(set(values), key=lambda v: (v != "", v.lower()))
        self._all_values = unique
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.list.clear()

        active = selected if selected is not None else set(unique)
        for value in unique:
            label = EMPTY_VALUE_LABEL if value == "" else value
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setData(Qt.UserRole, value)
            item.setCheckState(Qt.Checked if value in active else Qt.Unchecked)
            self.list.addItem(item)

        self.adjustSize()
        self.move(global_pos)
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def _request_sort(self, order: Qt.SortOrder) -> None:
        self.sort_requested.emit(self._column, int(order))
        self.close()

    def _filter_list(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            label = item.text().lower()
            item.setHidden(bool(needle) and needle not in label)

    def _check_all(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _uncheck_all(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)

    def _apply(self) -> None:
        checked: set[str] = set()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.Checked:
                checked.add(item.data(Qt.UserRole))
        if checked == set(self._all_values):
            self.applied.emit(self._column, None)
        else:
            self.applied.emit(self._column, checked)
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.closed.emit()
        super().closeEvent(event)


class ClickableImageLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ThumbnailScrollArea(QScrollArea):
    zoom_requested = Signal(int)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_requested.emit(1)
            elif delta < 0:
                self.zoom_requested.emit(-1)
            event.accept()
            return
        super().wheelEvent(event)


class PreviewPane(QFrame):
    """1フォルダ分のプレビュー枠。閉じるボタン付き。"""

    close_requested = Signal(object)  # emits self
    zoom_requested = Signal(int)

    def __init__(
        self,
        title: str,
        folder_path: Path,
        thumb_size: int,
        extensions: set[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.folder_path = folder_path
        self._thumb_size = thumb_size
        self._extensions = extensions or {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
        self._thumb_paths: list[Path] = []
        self.setObjectName("previewPane")
        self.setFrameShape(QFrame.StyledPanel)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: bold; background: transparent;")
        close_btn = QPushButton("閉じる")
        close_btn.setObjectName("previewCloseBtn")
        close_btn.setFixedHeight(30)
        close_btn.setMinimumWidth(72)
        close_btn.setToolTip("このプレビューを閉じる")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QPushButton#previewCloseBtn {
                background-color: #c0392b;
                color: #ffffff;
                border: 1px solid #96281b;
                border-radius: 4px;
                font-weight: bold;
                padding: 2px 12px;
            }
            QPushButton#previewCloseBtn:hover {
                background-color: #e74c3c;
            }
            QPushButton#previewCloseBtn:pressed {
                background-color: #96281b;
            }
            """
        )
        close_btn.clicked.connect(lambda: self.close_requested.emit(self))
        header.addWidget(self.title_label, 1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.scroll = ThumbnailScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.zoom_requested.connect(self.zoom_requested.emit)
        self.thumb_host = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_host)
        self.scroll.setWidget(self.thumb_host)
        layout.addWidget(self.scroll)

        self.load_images()

    def replace_content(self, title: str, folder_path: Path) -> None:
        self.title_label.setText(title)
        self.folder_path = folder_path
        self.load_images()

    def set_thumb_size(self, size: int) -> None:
        self._thumb_size = size
        self._render_thumbs()

    def load_images(self) -> None:
        self._thumb_paths = []
        if not self.folder_path.exists():
            self._render_thumbs()
            return
        exts = self._extensions
        files = [
            p
            for p in sorted(self.folder_path.iterdir())
            if p.is_file() and p.suffix.lower() in exts
        ]
        if not files:
            files = [
                p
                for p in sorted(self.folder_path.rglob("*"))
                if p.is_file() and p.suffix.lower() in exts
            ][:200]
        self._thumb_paths = files[:120]
        self._render_thumbs()

    def _render_thumbs(self) -> None:
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        size = self._thumb_size
        cols = max(1, self.scroll.viewport().width() // max(size + 24, 1))
        if not self._thumb_paths:
            empty = QLabel("(画像なし)")
            empty.setAlignment(Qt.AlignCenter)
            self.thumb_grid.addWidget(empty, 0, 0)
            return

        for idx, path in enumerate(self._thumb_paths):
            thumb = load_thumbnail(path, max_size=(size, size))
            label = ClickableImageLabel()
            label.setAlignment(Qt.AlignCenter)
            label.setCursor(Qt.PointingHandCursor)
            label.setToolTip(str(path))
            label.clicked.connect(lambda p=path: open_with_default_app(p))
            if thumb is not None:
                data = thumb.tobytes("raw", "RGB")
                qimg = QImage(
                    data, thumb.width, thumb.height, thumb.width * 3, QImage.Format_RGB888
                )
                pix = QPixmap.fromImage(qimg.copy())
                label.setPixmap(pix)
            else:
                label.setText("(読込失敗)")
            caption = QLabel(path.name)
            caption.setWordWrap(True)
            caption.setMaximumWidth(size + 20)
            cell = QWidget()
            v = QVBoxLayout(cell)
            v.setContentsMargins(4, 4, 4, 4)
            v.addWidget(label)
            v.addWidget(caption)
            self.thumb_grid.addWidget(cell, idx // cols, idx % cols)


class BrowseTab(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.repo = Repository(db.connection)
        self.tag_service = TagService(self.repo)
        self.current_sem: SemCase | None = None
        self.current_folder_id: int | None = None
        self._thumb_size = 160
        self._loading_table = False
        self._preview_panes: list[PreviewPane] = []
        # folder_key -> pane （同じフォルダの二重表示を防ぐ）
        self._pane_keys: dict[str, PreviewPane] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(True)
        root.addWidget(self.main_splitter)

        top = QWidget()
        top.setMinimumHeight(120)
        top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        search_box = QGroupBox("検索 / タグ")
        search_form = QHBoxLayout(search_box)
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("キーワード（全体）")
        self.tag_filter = QListWidget()
        self.tag_filter.setSelectionMode(QListWidget.MultiSelection)
        self.tag_filter.setMaximumHeight(56)
        self.tag_filter.setMaximumWidth(220)
        search_btn = QPushButton("再読込")
        search_btn.clicked.connect(self.reload_table)
        search_form.addWidget(self.query_edit, 1)
        search_form.addWidget(self.tag_filter)
        search_form.addWidget(search_btn)
        top_layout.addWidget(search_box)

        btn_row = QHBoxLayout()
        explorer_btn = QPushButton("エクスプローラーで開く")
        explorer_btn.clicked.connect(self._open_explorer)
        tag_btn = QPushButton("タグ編集")
        tag_btn.clicked.connect(self._edit_tags)
        zoom_out = QPushButton("サムネ −")
        zoom_out.clicked.connect(lambda: self._change_thumb_size(-1))
        zoom_in = QPushButton("サムネ ＋")
        zoom_in.clicked.connect(lambda: self._change_thumb_size(1))
        clear_previews = QPushButton("プレビュー全閉じ")
        clear_previews.clicked.connect(self._clear_all_panes)
        self.zoom_label = QLabel(self._zoom_hint())
        btn_row.addWidget(explorer_btn)
        btn_row.addWidget(tag_btn)
        btn_row.addWidget(zoom_out)
        btn_row.addWidget(zoom_in)
        btn_row.addWidget(clear_previews)
        clear_col_filters = QPushButton("列フィルタ解除")
        clear_col_filters.clicked.connect(self._clear_column_filters)
        btn_row.addWidget(clear_col_filters)
        btn_row.addWidget(self.zoom_label)
        btn_row.addStretch()
        top_layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(HEADERS))
        self._update_header_labels()
        # ヘッダークリックはフィルタポップアップ専用。ソートはポップアップ内ボタンで行う
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        for col in range(len(HEADERS)):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemChanged.connect(self._on_item_changed)
        top_layout.addWidget(self.table, 1)
        self.main_splitter.addWidget(top)

        # col -> selected values (None = no filter)
        self._column_value_filters: dict[int, set[str] | None] = {
            i: None for i in range(len(HEADERS))
        }
        self._filter_popup = ColumnFilterPopup(self)
        self._filter_popup.applied.connect(self._on_filter_applied)
        self._filter_popup.sort_requested.connect(self._on_sort_requested)

        bottom = QWidget()
        bottom.setMinimumHeight(80)
        bottom.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(
            QLabel(
                "画像プレビュー（1枚のときはパス列クリックで表示・切替 / "
                "2枚以上は Ctrl+クリックで追加・最大4分割 / 閉じるボタンで個別クローズ）"
            )
        )
        self.preview_splitter = QSplitter(Qt.Horizontal)
        self.preview_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_layout.addWidget(self.preview_splitter, 1)
        self.main_splitter.addWidget(bottom)
        # 上:下 = ほぼ同等。上の伸長優位をやめて、下へ広げやすくする
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([320, 420])

        self.reload_table()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._reload_tag_filter()

    def refresh_case_list(self) -> None:
        self.reload_table()

    def _update_header_labels(self) -> None:
        labels = []
        for i, name in enumerate(HEADERS):
            active = getattr(self, "_column_value_filters", {}).get(i) is not None
            labels.append(f"▾ {name}" if active else f"▼ {name}")
        self.table.setHorizontalHeaderLabels(labels)

    def _clear_column_filters(self) -> None:
        self._column_value_filters = {i: None for i in range(len(HEADERS))}
        self._update_header_labels()
        self._apply_column_filters()

    def _on_header_clicked(self, section: int) -> None:
        # クリックでソートも走るので、フィルタポップアップを優先表示
        values: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, section)
            values.append(item.text() if item else "")
        header = self.table.horizontalHeader()
        x = header.sectionViewportPosition(section)
        pos = header.mapToGlobal(header.rect().bottomLeft())
        pos.setX(header.mapToGlobal(header.rect().topLeft()).x() + x)
        self._filter_popup.open_for(
            section,
            values,
            self._column_value_filters.get(section),
            pos,
        )

    def _on_filter_applied(self, column: int, selected) -> None:
        self._column_value_filters[column] = selected
        self._update_header_labels()
        self._apply_column_filters()

    def _on_sort_requested(self, column: int, order: int) -> None:
        self.table.setSortingEnabled(True)
        self.table.sortItems(column, Qt.SortOrder(order))
        self.table.horizontalHeader().setSortIndicator(column, Qt.SortOrder(order))
        self.table.setSortingEnabled(False)
        self._apply_column_filters()

    def _apply_column_filters(self) -> None:
        for row in range(self.table.rowCount()):
            visible = True
            for col, selected in self._column_value_filters.items():
                if selected is None:
                    continue
                item = self.table.item(row, col)
                value = item.text() if item else ""
                if value not in selected:
                    visible = False
                    break
            self.table.setRowHidden(row, not visible)

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

    def reload_table(self) -> None:
        self._reload_tag_filter()
        tag_ids = [
            item.data(Qt.UserRole)
            for item in self.tag_filter.selectedItems()
            if item.data(Qt.UserRole) is not None
        ]
        filters = SearchFilters(
            query=self.query_edit.text(),
            tag_ids=tag_ids,
        )
        matched_sems = {c.id for c in self.repo.search_sem_cases(filters) if c.id is not None}
        pairs = self.repo.list_all_folders()
        if filters.query or filters.tag_ids:
            pairs = [(s, f) for s, f in pairs if s.id in matched_sems]
            q = filters.query.strip().lower()
            if q:
                refined: list[tuple[SemCase, FolderRecord]] = []
                for sem, folder in pairs:
                    blob = " ".join(
                        [
                            sem.request_no,
                            folder.relative_path,
                            folder.substrate,
                            folder.lot_name,
                            folder.lot_id,
                            folder.process,
                            folder.condition,
                            folder.memo,
                            folder.slot_id or "",
                        ]
                    ).lower()
                    if q not in blob:
                        continue
                    refined.append((sem, folder))
                pairs = refined

        self._loading_table = True
        self.table.setRowCount(0)
        for sem, folder in pairs:
            assert folder.id is not None and sem.id is not None
            display = f"{sem.request_no} - {folder.relative_path.replace('/', ' - ')}"
            row = self.table.rowCount()
            self.table.insertRow(row)
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
                        "local_path": sem.local_path,
                        "display": display,
                    },
                )
                if col == COL_PATH:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        self._loading_table = False
        self._apply_column_filters()
        self._update_header_labels()
        # 再読込でも開いているプレビューは維持（勝手に消えない）
        self.current_folder_id = None
        self.current_sem = None

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        col = item.column()
        field = FIELD_BY_COL.get(col)
        if not field:
            return
        data = item.data(Qt.UserRole) or {}
        folder_id = data.get("folder_id")
        if folder_id is None:
            path_item = self.table.item(item.row(), COL_PATH)
            data = (path_item.data(Qt.UserRole) if path_item else {}) or {}
            folder_id = data.get("folder_id")
        if folder_id is None:
            return
        try:
            self.repo.update_folder_field(int(folder_id), field, item.text())
            sem_id = data.get("sem_id")
            if sem_id is None:
                path_item = self.table.item(item.row(), COL_PATH)
                sem_id = (path_item.data(Qt.UserRole) or {}).get("sem_id") if path_item else None
            if sem_id is not None:
                write_sem_info_file(self.repo, int(sem_id))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "保存エラー", str(exc))

    def _selected_row_indices(self) -> list[int]:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        return rows

    def _row_data(self, row: int) -> dict:
        path_item = self.table.item(row, COL_PATH)
        if not path_item:
            return {}
        return path_item.data(Qt.UserRole) or {}

    def _zoom_hint(self, *, status: str | None = None) -> str:
        base = (
            f"サムネ {self._thumb_size}px"
            f"（1枚時は番号クリックで切替 / 2枚以上はCtrl+番号クリックで追加・最大{MAX_PREVIEW_PANES}"
            f" / Ctrl+ホイールでズーム）"
        )
        return f"{base} — {status}" if status else base

    def _preview_payload(self, row: int) -> tuple[str, str, Path] | None:
        data = self._row_data(row)
        local_path = data.get("local_path", "")
        rel = data.get("relative_path", "")
        display = data.get("display") or rel
        if not local_path:
            return None
        folder_path = Path(local_path) / rel
        key = str(folder_path.resolve()) if folder_path.exists() else str(folder_path)
        return key, display, folder_path

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column != COL_PATH:
            return
        ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        pane_count = len(self._preview_panes)

        if pane_count <= 1 and not ctrl:
            if pane_count == 0:
                self._try_add_preview_for_row(row)
            else:
                self._switch_single_preview(row)
            return

        if ctrl:
            self._try_add_preview_for_row(row)

    def _switch_single_preview(self, row: int) -> bool:
        payload = self._preview_payload(row)
        if payload is None:
            return False
        key, display, folder_path = payload
        if key in self._pane_keys:
            self.zoom_label.setText(self._zoom_hint(status="すでにプレビュー表示中"))
            return False

        pane = self._preview_panes[0]
        old_key = next((k for k, p in self._pane_keys.items() if p is pane), None)
        if old_key is not None:
            del self._pane_keys[old_key]
        self._pane_keys[key] = pane
        pane.replace_content(display, folder_path)
        self.zoom_label.setText(self._zoom_hint(status="プレビューを切り替えました"))
        return True

    def _try_add_preview_for_row(self, row: int) -> bool:
        payload = self._preview_payload(row)
        if payload is None:
            return False
        key, display, folder_path = payload
        if key in self._pane_keys:
            self.zoom_label.setText(self._zoom_hint(status="すでにプレビュー表示中"))
            return False
        if len(self._preview_panes) >= MAX_PREVIEW_PANES:
            self.zoom_label.setText(
                self._zoom_hint(status=f"上限{MAX_PREVIEW_PANES}分割。閉じるで1枚減らしてから追加")
            )
            return False
        self._add_pane(key, display, folder_path)
        self.zoom_label.setText(
            self._zoom_hint(status=f"プレビュー {len(self._preview_panes)}/{MAX_PREVIEW_PANES}")
        )
        return True

    def _on_row_selected(self) -> None:
        rows = self._selected_row_indices()
        if not rows:
            return

        first = self._row_data(rows[0])
        self.current_folder_id = first.get("folder_id")
        sem_id = first.get("sem_id")
        self.current_sem = self.repo.get_sem(sem_id) if sem_id else None

    def _add_pane(self, key: str, title: str, folder_path: Path) -> None:
        # 追加前後でメイン上下スプリットの位置を保持
        main_sizes = self.main_splitter.sizes()
        preview_sizes = self.preview_splitter.sizes()

        pane = PreviewPane(
            title,
            folder_path,
            self._thumb_size,
            extensions=self.db.get_settings().extension_set(),
        )
        pane.close_requested.connect(self._remove_pane)
        pane.zoom_requested.connect(self._change_thumb_size)
        self._preview_panes.append(pane)
        self._pane_keys[key] = pane
        self.preview_splitter.addWidget(pane)

        # 横分割は均等寄りに、上下は元サイズ維持
        count = len(self._preview_panes)
        if count > 0:
            total = sum(preview_sizes) if preview_sizes and sum(preview_sizes) > 0 else 800
            self.preview_splitter.setSizes([max(80, total // count)] * count)
        if main_sizes and sum(main_sizes) > 0:
            self.main_splitter.setSizes(main_sizes)

    def _remove_pane(self, pane: PreviewPane) -> None:
        main_sizes = self.main_splitter.sizes()
        key = None
        for k, p in self._pane_keys.items():
            if p is pane:
                key = k
                break
        if key is not None:
            del self._pane_keys[key]
        if pane in self._preview_panes:
            self._preview_panes.remove(pane)
        pane.setParent(None)
        pane.deleteLater()
        if main_sizes and sum(main_sizes) > 0:
            self.main_splitter.setSizes(main_sizes)
        self.zoom_label.setText(
            self._zoom_hint(status=f"プレビュー {len(self._preview_panes)}/{MAX_PREVIEW_PANES}")
        )

    def _clear_all_panes(self) -> None:
        main_sizes = self.main_splitter.sizes()
        for pane in list(self._preview_panes):
            self._remove_pane(pane)
        if main_sizes and sum(main_sizes) > 0:
            self.main_splitter.setSizes(main_sizes)

    def _edit_tags(self) -> None:
        if self.current_folder_id is not None:
            dlg = TagEditorDialog(self.tag_service, "folder", self.current_folder_id, self)
        elif self.current_sem and self.current_sem.id is not None:
            dlg = TagEditorDialog(self.tag_service, "sem", self.current_sem.id, self)
        else:
            QMessageBox.information(self, "タグ", "行を選択してください")
            return
        dlg.exec()
        self._reload_tag_filter()

    def _open_explorer(self) -> None:
        rows = self._selected_row_indices()
        if not rows:
            QMessageBox.information(self, "開く", "行を選択してください")
            return
        data = self._row_data(rows[0])
        local_path = data.get("local_path", "")
        rel = data.get("relative_path", "")
        if not local_path:
            return
        open_in_explorer(Path(local_path) / rel)

    def _change_thumb_size(self, direction: int) -> None:
        new_size = self._thumb_size + (40 * direction)
        self._thumb_size = max(60, min(480, new_size))
        self.zoom_label.setText(self._zoom_hint())
        for pane in self._preview_panes:
            pane.set_thumb_size(self._thumb_size)
