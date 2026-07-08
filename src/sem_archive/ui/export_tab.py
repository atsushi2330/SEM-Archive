from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.models import AppSettings
from sem_archive.services.ppt_export import PptExportService


class ExportTab(QWidget):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.repo = Repository(db.connection)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("抽出したい SEM / フォルダにチェックを入れてください（配下画像が対象）"))

        opts = QHBoxLayout()
        opts.addWidget(QLabel("ページ分け"))
        self.page_mode = QComboBox()
        self.page_mode.addItem("Slot単位", "slot")
        self.page_mode.addItem("フラット（分けない）", "flat")
        opts.addWidget(self.page_mode)

        opts.addWidget(QLabel("行分け"))
        self.row_mode = QComboBox()
        self.row_mode.addItem("サブフォルダ（例: C/M/E）", "subdir")
        self.row_mode.addItem("行分けなし", "none")
        opts.addWidget(self.row_mode)

        opts.addWidget(QLabel("1行枚数"))
        self.per_row = QSpinBox()
        self.per_row.setRange(1, 20)
        settings = db.get_settings()
        self.per_row.setValue(settings.images_per_row)
        opts.addWidget(self.per_row)
        opts.addStretch()
        layout.addLayout(opts)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["対象", "Slot", "条件/メモ"])
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        refresh = QPushButton("一覧更新")
        refresh.clicked.connect(self.reload)
        export_btn = QPushButton("PowerPointへ出力")
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(refresh)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

        self.reload()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        self.tree.clear()
        settings = self.db.get_settings()
        idx = self.page_mode.findData(settings.export_page_mode)
        if idx >= 0:
            self.page_mode.setCurrentIndex(idx)
        idx = self.row_mode.findData(settings.export_row_mode)
        if idx >= 0:
            self.row_mode.setCurrentIndex(idx)
        self.per_row.setValue(settings.images_per_row)

        for case in self.repo.list_sem_cases():
            assert case.id is not None
            top = QTreeWidgetItem([case.request_no, "", (case.condition or case.memo)[:60]])
            top.setFlags(top.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            top.setCheckState(0, Qt.Unchecked)
            top.setData(0, Qt.UserRole, {"type": "sem", "id": case.id})
            self.tree.addTopLevelItem(top)
            folders = self.repo.list_folders(case.id)
            nodes: dict[str, QTreeWidgetItem] = {}
            for folder in folders:
                node = QTreeWidgetItem(
                    [
                        folder.folder_name,
                        folder.slot_id or "",
                        (folder.condition or folder.memo)[:60],
                    ]
                )
                node.setFlags(node.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                node.setCheckState(0, Qt.Unchecked)
                node.setData(0, Qt.UserRole, {"type": "folder", "id": folder.id, "sem_id": case.id})
                nodes[folder.relative_path] = node
                if "/" in folder.relative_path:
                    parent_rel = folder.relative_path.rsplit("/", 1)[0]
                    parent = nodes.get(parent_rel, top)
                    parent.addChild(node)
                else:
                    top.addChild(node)
        self.tree.expandToDepth(1)

    def _collect_selection(self) -> dict[int, list[int]]:
        """sem_id -> folder_ids。SEMだけチェックなら folder_ids 空（全体）。"""
        result: dict[int, list[int]] = {}
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            data = top.data(0, Qt.UserRole) or {}
            sem_id = data.get("id")
            if sem_id is None:
                continue
            folder_ids: list[int] = []
            self._collect_checked_folders(top, folder_ids)
            if top.checkState(0) == Qt.Checked and not folder_ids:
                result[sem_id] = []  # 全体
            elif folder_ids:
                result[sem_id] = folder_ids
            elif top.checkState(0) == Qt.PartiallyChecked and folder_ids:
                result[sem_id] = folder_ids
        return result

    def _collect_checked_folders(self, item: QTreeWidgetItem, out: list[int]) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            data = child.data(0, Qt.UserRole) or {}
            if data.get("type") == "folder" and child.checkState(0) in (Qt.Checked, Qt.PartiallyChecked):
                # 自分が Checked で子も全部含むならこのフォルダIDだけでよい
                if child.checkState(0) == Qt.Checked:
                    out.append(int(data["id"]))
                else:
                    self._collect_checked_folders(child, out)
            else:
                self._collect_checked_folders(child, out)

    def _export(self) -> None:
        selection = self._collect_selection()
        if not selection:
            QMessageBox.warning(self, "未選択", "SEMまたはフォルダをチェックしてください")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PowerPointの保存先", "sem_export.pptx", "PowerPoint (*.pptx)"
        )
        if not path:
            return

        settings = self.db.get_settings()
        settings.export_page_mode = self.page_mode.currentData()
        settings.export_row_mode = self.row_mode.currentData()
        settings.images_per_row = self.per_row.value()
        self.db.save_settings(settings)

        semis = []
        selection_map: dict[int, list[int]] = {}
        for sem_id, folder_ids in selection.items():
            case = self.repo.get_sem(sem_id)
            if not case:
                continue
            semis.append(case)
            # 空リストは全体。サービス側は None/空で全体扱いなので、
            # 空のときはキーを入れない or None 渡しにする
            if folder_ids:
                selection_map[sem_id] = folder_ids
            else:
                selection_map[sem_id] = []

        service = PptExportService(self.repo, settings)
        # folder_ids が空 = SEM全体。collect で selected_folder_ids=[] だと
        # falsy 扱いで全体になるよう export 側を調整済みにする
        try:
            # 空リストは全体にしたいので、export 内で特別扱い
            out = self._export_with_empty_means_all(service, Path(path), semis, selection_map)
            QMessageBox.information(self, "完了", f"出力しました:\n{out}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "エラー", str(exc))

    def _export_with_empty_means_all(
        self,
        service: PptExportService,
        output_path: Path,
        semis: list,
        selection_map: dict[int, list[int]],
    ) -> Path:
        from pptx import Presentation
        from pptx.util import Inches

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        cache_dir = output_path.parent / "_tiff_cache"

        for sem in semis:
            assert sem.id is not None
            folder_ids = selection_map.get(sem.id)
            if folder_ids is not None and len(folder_ids) == 0:
                items = service.collect_images(sem, selected_folder_ids=None)
            else:
                items = service.collect_images(sem, selected_folder_ids=folder_ids)
            if not items:
                continue
            pages = service._group_by_page(items)
            for page_key, page_items in pages:
                rows = service._group_by_row(page_items)
                service._render_page_groups(prs, sem.request_no, page_key, rows, cache_dir)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
        return output_path
