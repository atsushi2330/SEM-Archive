from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.models import AppSettings, SemCase
from sem_archive.services.copy_service import ScanService
from sem_archive.services.ppt_export import PptExportService
from sem_archive.utils.paths import normalize_request_nos, relative_label
from sem_archive.utils.slot_detect import detect_slot_id, is_slot_folder


@pytest.mark.parametrize(
    "name,expected",
    [
        ("s1", "S1"),
        ("S1", "S1"),
        ("slot1", "S1"),
        ("Slot01", "S1"),
        ("SLOT12", "S12"),
        ("1", "S1"),
        ("C", None),
        ("M", None),
        ("E", None),
        ("sample", None),
    ],
)
def test_detect_slot_id(name: str, expected: str | None) -> None:
    assert detect_slot_id(name) == expected
    assert is_slot_folder(name) is (expected is not None)


def test_normalize_request_nos() -> None:
    text = "202607080211\n202607080212, 202607080213 202607080211"
    assert normalize_request_nos(text) == [
        "202607080211",
        "202607080212",
        "202607080213",
    ]


def test_relative_label(tmp_path: Path) -> None:
    sem = tmp_path / "202607080211"
    img = sem / "S1" / "C" / "a.jpg"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"x")
    assert relative_label(sem, img) == "S1/C/a.jpg"


def test_db_schema_and_tags(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db.connection)
    cats = repo.list_categories()
    names = {c.name for c in cats}
    assert {"下地", "工程", "評価内容"} <= names

    settings = db.get_settings()
    settings.local_root = str(tmp_path / "local")
    settings.server_root = str(tmp_path / "server")
    db.save_settings(settings)
    loaded = db.get_settings()
    assert loaded.local_root.endswith("local")


def test_scan_and_ppt_export(tmp_path: Path) -> None:
    server = tmp_path / "server" / "202607080211"
    (server / "S1" / "C").mkdir(parents=True)
    (server / "S1" / "M").mkdir(parents=True)
    (server / "S2" / "E").mkdir(parents=True)
    for folder, name in [
        (server / "S1" / "C", "c1.jpg"),
        (server / "S1" / "M", "m1.jpg"),
        (server / "S2" / "E", "e1.tif"),
    ]:
        Image.new("RGB", (80, 60), color=(120, 40, 40)).save(folder / name)

    local_root = tmp_path / "local"
    # テストではコピー済み想定で local に直接置く
    import shutil

    shutil.copytree(server, local_root / "202607080211")

    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db.connection)
    case = repo.upsert_sem_case(
        SemCase(
            id=None,
            request_no="202607080211",
            memo="memo",
            condition="cond-A",
            local_path=str(local_root / "202607080211"),
            imported_at="2026-07-08 00:00:00",
        )
    )
    assert case.id is not None
    repo.set_lots(case.id, ["LOT001", "LOT002"])
    folders = ScanService.build_folder_records(case.id, Path(case.local_path))
    saved = repo.replace_folders(case.id, folders)
    assert any(f.is_slot and f.slot_id == "S1" for f in saved)

    settings = AppSettings(
        server_root=str(tmp_path / "server"),
        local_root=str(local_root),
        images_per_row=10,
        export_page_mode="slot",
        export_row_mode="subdir",
    )
    service = PptExportService(repo, settings)
    items = service.collect_images(case)
    assert len(items) == 3
    assert all("LotID:LOT001, LOT002" in i.alt_text for i in items)
    assert any(i.page_key == "S1" for i in items)

    out = tmp_path / "out.pptx"
    service.export(out, [case])
    assert out.exists() and out.stat().st_size > 0

    # フォルダ直編集フィールドの永続化
    slot_folder = next(f for f in saved if f.slot_id == "S1")
    assert slot_folder.id is not None
    repo.update_folder_field(slot_folder.id, "substrate", "Si")
    repo.update_folder_field(slot_folder.id, "lot_name", "Alpha")
    repo.update_folder_field(slot_folder.id, "lot_id", "L-9")
    repo.update_folder_field(slot_folder.id, "process", "Etch")
    updated = repo.get_folder(slot_folder.id)
    assert updated is not None
    assert updated.substrate == "Si"
    assert updated.lot_name == "Alpha"
    assert updated.lot_id == "L-9"
    assert updated.process == "Etch"

    # 既存DBへのカラム migration
    db2 = Database(tmp_path / "test.db")
    db2.initialize()
    cols = {r[1] for r in db2.connection.execute("PRAGMA table_info(folders)").fetchall()}
    assert {"substrate", "lot_name", "lot_id", "process"} <= cols
