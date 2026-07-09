from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sem_archive.db.repository import Repository
from sem_archive.models import AppSettings, FolderRecord, SemCase
from sem_archive.services.metadata_export import write_sem_info_file
from sem_archive.utils.slot_detect import detect_slot_id


@dataclass
class ImportResult:
    request_no: str
    success: bool
    message: str
    sem_case_id: int | None = None


class CopyService:
    def __init__(self, repo: Repository, settings: AppSettings) -> None:
        self.repo = repo
        self.settings = settings

    def import_cases(
        self,
        request_nos: list[str],
        lot_nos: list[str] | None = None,
        memo: str = "",
        condition: str = "",
    ) -> list[ImportResult]:
        results: list[ImportResult] = []
        server_root = Path(self.settings.server_root)
        local_root = Path(self.settings.local_root)
        if not self.settings.server_root:
            return [
                ImportResult(no, False, "サーバールートが未設定です") for no in request_nos
            ]
        if not self.settings.local_root:
            return [
                ImportResult(no, False, "ローカル保存先が未設定です") for no in request_nos
            ]
        local_root.mkdir(parents=True, exist_ok=True)

        for request_no in request_nos:
            src = server_root / request_no
            dst = local_root / request_no
            if not src.exists():
                results.append(ImportResult(request_no, False, f"サーバーに見つかりません: {src}"))
                continue
            try:
                if dst.exists():
                    # 既存を更新コピー（上書き）
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copytree(src, dst)
                imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                case = self.repo.upsert_sem_case(
                    SemCase(
                        id=None,
                        request_no=request_no,
                        memo=memo,
                        condition=condition,
                        local_path=str(dst),
                        imported_at=imported_at,
                    )
                )
                assert case.id is not None
                if lot_nos is not None:
                    self.repo.set_lots(case.id, lot_nos)
                folders = ScanService.build_folder_records(case.id, dst)
                self.repo.replace_folders(case.id, folders)
                write_sem_info_file(self.repo, case.id)
                results.append(
                    ImportResult(request_no, True, f"取込完了: {dst}", sem_case_id=case.id)
                )
            except Exception as exc:  # noqa: BLE001
                results.append(ImportResult(request_no, False, str(exc)))
        return results


class ScanService:
    @staticmethod
    def build_folder_records(sem_case_id: int, sem_root: Path) -> list[FolderRecord]:
        records: list[FolderRecord] = []
        if not sem_root.exists():
            return records
        for path in sorted(p for p in sem_root.rglob("*") if p.is_dir()):
            rel = path.relative_to(sem_root).as_posix()
            slot = detect_slot_id(path.name)
            records.append(
                FolderRecord(
                    id=None,
                    sem_case_id=sem_case_id,
                    relative_path=rel,
                    folder_name=path.name,
                    slot_id=slot,
                    is_slot=slot is not None,
                )
            )
        return records

    @staticmethod
    def rescan(repo: Repository, sem_case_id: int, local_path: str) -> list[FolderRecord]:
        folders = ScanService.build_folder_records(sem_case_id, Path(local_path))
        return repo.replace_folders(sem_case_id, folders)
