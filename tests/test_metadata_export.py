from __future__ import annotations

from pathlib import Path

from sem_archive.db.connection import Database
from sem_archive.db.repository import Repository
from sem_archive.models import SemCase
from sem_archive.services.copy_service import ScanService
from sem_archive.services.metadata_export import info_filename_for, write_sem_info_file


def test_write_sem_info_file(tmp_path: Path) -> None:
    sem_root = tmp_path / "202607080211" / "S1"
    sem_root.mkdir(parents=True)

    db = Database(tmp_path / "test.db")
    db.initialize()
    repo = Repository(db.connection)
    case = repo.upsert_sem_case(
        SemCase(
            id=None,
            request_no="202607080211",
            memo="全体メモ",
            condition="全体条件",
            local_path=str(tmp_path / "202607080211"),
            imported_at="2026-07-10 00:00:00",
        )
    )
    assert case.id is not None
    repo.set_lots(case.id, ["LOT-A"])
    folders = ScanService.build_folder_records(case.id, Path(case.local_path))
    saved = repo.replace_folders(case.id, folders)
    slot = next(f for f in saved if f.slot_id == "S1")
    assert slot.id is not None
    repo.update_folder_field(slot.id, "lot_name", "Alpha")
    repo.update_folder_field(slot.id, "lot_id", "L-001")
    repo.update_folder_field(slot.id, "substrate", "Si")

    out = write_sem_info_file(repo, case.id)
    assert out is not None
    assert out.name == info_filename_for("202607080211")
    text = out.read_text(encoding="utf-8")
    assert "202607080211" in text
    assert "LOT-A" in text
    assert "Alpha" in text
    assert "L-001" in text
    assert "Si" in text
    assert "SEM-Archive メタデータ" not in text
    assert "SEM-Archive により自動生成" not in text
