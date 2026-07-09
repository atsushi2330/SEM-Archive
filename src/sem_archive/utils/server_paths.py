from __future__ import annotations

import os
from pathlib import Path


def normalize_server_path(path: str) -> str:
    """サーバーパスを正規化する（UNC・末尾スラッシュ等）。"""
    p = path.strip()
    if not p:
        return ""
    if p.startswith("\\\\"):
        return p.replace("/", "\\").rstrip("\\")
    return str(Path(p))


def list_immediate_subdirs(root_path: str) -> tuple[list[str], str | None]:
    """サーバールート直下のフォルダ名一覧を返す。失敗時は ([], エラーメッセージ)。"""
    root = normalize_server_path(root_path)
    if not root:
        return [], "パスが空です"

    is_unc = root.startswith("\\\\")
    if not is_unc:
        try:
            root_p = Path(root)
            if not root_p.exists():
                return [], f"パスが見つかりません: {root}"
            if not root_p.is_dir():
                return [], f"フォルダではありません: {root}"
        except OSError as exc:
            return [], f"パスを確認できません: {exc}"

    names: list[str] = []
    last_error: OSError | None = None

    for scan_root in (root,):
        try:
            with os.scandir(scan_root) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            names.append(entry.name)
                    except OSError:
                        continue
            return sorted(names, key=str.lower), None
        except OSError as exc:
            last_error = exc

    if last_error is not None:
        try:
            for name in os.listdir(root):
                full = os.path.join(root, name)
                try:
                    if os.path.isdir(full):
                        names.append(name)
                except OSError:
                    continue
            if names:
                return sorted(names, key=str.lower), None
            return [], f"フォルダを読めません: {last_error}"
        except OSError as exc:
            return [], f"フォルダを読めません: {exc}"

    return [], "フォルダを読めません"

