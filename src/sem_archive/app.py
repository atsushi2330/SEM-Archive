from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from sem_archive.db.connection import Database
from sem_archive.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SEM-Archive")
    app.setOrganizationName("SEM-Archive")

    db = Database.default()
    db.initialize()

    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
