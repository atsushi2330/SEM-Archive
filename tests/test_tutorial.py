import sys

from PySide6.QtWidgets import QApplication

from sem_archive.ui.tutorial import TutorialDialog


def test_tutorial_dialog() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = TutorialDialog()
    assert dlg.windowTitle() == "チュートリアル"
