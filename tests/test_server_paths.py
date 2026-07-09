from pathlib import Path

from sem_archive.utils.server_paths import list_immediate_subdirs, normalize_server_path


def test_normalize_server_path() -> None:
    assert normalize_server_path("  \\\\server\\share\\  ") == "\\\\server\\share"
    assert normalize_server_path("") == ""


def test_list_immediate_subdirs(tmp_path: Path) -> None:
    (tmp_path / "202607080211").mkdir()
    (tmp_path / "202607080212").mkdir()
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")

    names, err = list_immediate_subdirs(str(tmp_path))
    assert err is None
    assert names == ["202607080211", "202607080212"]

    names2, err2 = list_immediate_subdirs(str(tmp_path / "missing"))
    assert names2 == []
    assert err2 is not None


def test_server_folder_picker_dialog(tmp_path: Path) -> None:
    (tmp_path / "202607080211").mkdir()
    import sys

    from PySide6.QtWidgets import QApplication

    from sem_archive.ui.dialogs import ServerFolderPickerDialog

    app = QApplication.instance() or QApplication(sys.argv)
    dlg = ServerFolderPickerDialog(str(tmp_path), {"202607080211"})
    assert dlg.list_widget.count() == 1
    item = dlg.list_widget.item(0)
    assert item is not None
    assert item.text() == "202607080211"
    from PySide6.QtCore import Qt

    assert item.checkState() == Qt.CheckState.Checked
