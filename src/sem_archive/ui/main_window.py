from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from sem_archive.db.connection import Database
from sem_archive.ui.browse_tab import BrowseTab
from sem_archive.ui.dialogs import SettingsDialog
from sem_archive.ui.export_tab import ExportTab
from sem_archive.ui.import_tab import ImportTab
from sem_archive.ui.themes import apply_theme
from sem_archive.ui.tutorial import TutorialDialog


class MainWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle("SEM-Archive")
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.import_tab = ImportTab(db)
        self.browse_tab = BrowseTab(db)
        self.export_tab = ExportTab(db)
        self.tabs.addTab(self.import_tab, "取込")
        self.tabs.addTab(self.browse_tab, "閲覧")
        self.tabs.addTab(self.export_tab, "抽出")
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.import_tab.data_changed.connect(self.browse_tab.reload_table)
        self.import_tab.data_changed.connect(self.export_tab.reload)

        settings_action = QAction("環境設定", self)
        settings_action.triggered.connect(self._open_settings)
        tutorial_action = QAction("チュートリアル", self)
        tutorial_action.triggered.connect(self._open_tutorial)
        self.menuBar().addAction(settings_action)
        self.menuBar().addAction(tutorial_action)

    def _open_tutorial(self) -> None:
        TutorialDialog(self).exec()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.db, self)
        if dlg.exec():
            apply_theme(QApplication.instance(), self.db.get_settings().theme_id)
            self.browse_tab.refresh_case_list()
            self.export_tab.reload()

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        # 閲覧タブに戻るたびにフル再読込するとプレビューが消えて動くのでやめる
        if widget is self.export_tab:
            self.export_tab.reload()
