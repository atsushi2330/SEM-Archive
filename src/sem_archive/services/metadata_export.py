from __future__ import annotations

from pathlib import Path

from sem_archive.db.repository import Repository


def info_filename_for(request_no: str) -> str:
    """SEM依頼フォルダ内の説明テキストファイル名（例: 202607080211_説明.txt）。"""
    return f"{request_no}_説明.txt"


def write_sem_info_file(repo: Repository, sem_case_id: int) -> Path | None:
    """SEM依頼フォルダ内に、ソフト未使用でも読める説明テキストを出力する。"""
    case = repo.get_sem(sem_case_id)
    if not case or not case.local_path:
        return None
    root = Path(case.local_path)
    if not root.exists():
        return None

    lots = repo.list_lots(sem_case_id)
    folders = repo.list_folders(sem_case_id)
    lines: list[str] = [
        f"SEM依頼番号: {case.request_no}",
        f"取込日時: {case.imported_at or '-'}",
        f"条件（SEM全体）: {case.condition or '-'}",
        f"メモ（SEM全体）: {case.memo or '-'}",
        f"Lot番号: {', '.join(l.lot_no for l in lots) if lots else '-'}",
        "",
        "【フォルダ別メタデータ】",
    ]
    if not folders:
        lines.append("（サブフォルダなし）")
    else:
        for folder in folders:
            lines.extend(
                [
                    "",
                    f"--- {folder.relative_path or '(ルート)'} ---",
                    f"  Slot: {folder.slot_id or '-'}",
                    f"  下地: {folder.substrate or '-'}",
                    f"  Lot Name: {folder.lot_name or '-'}",
                    f"  Lot ID: {folder.lot_id or '-'}",
                    f"  工程: {folder.process or '-'}",
                    f"  条件: {folder.condition or '-'}",
                    f"  メモ: {folder.memo or '-'}",
                ]
            )

    out = root / info_filename_for(case.request_no)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_all_sem_info_files(repo: Repository, sem_case_ids: list[int]) -> list[Path]:
    written: list[Path] = []
    for sem_id in sem_case_ids:
        path = write_sem_info_file(repo, sem_id)
        if path:
            written.append(path)
    return written
