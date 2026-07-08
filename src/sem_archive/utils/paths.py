from __future__ import annotations

import re
from pathlib import Path


def normalize_request_nos(text: str) -> list[str]:
    """カンマ / 空白 / 改行区切りの SEM依頼番号を一意リストにする。"""
    parts = re.split(r"[\s,;]+", text.strip())
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        value = part.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def safe_join(root: Path, *parts: str) -> Path:
    return root.joinpath(*parts)


def relative_label(sem_root: Path, image_path: Path) -> str:
    """SEM依頼番号フォルダより下の相対パス（ラベル用）。"""
    try:
        return image_path.relative_to(sem_root).as_posix()
    except ValueError:
        return image_path.name


def iter_image_files(folder: Path, extensions: set[str]) -> list[Path]:
    if not folder.exists():
        return []
    files: list[Path] = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in extensions:
            files.append(path)
    return files


def open_in_explorer(path: Path) -> None:
    import os
    import subprocess
    import sys

    target = str(path if path.exists() else path.parent)
    if sys.platform.startswith("win"):
        if path.is_file():
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", target], check=False)
    else:
        subprocess.run(["xdg-open", target], check=False)


def open_with_default_app(path: Path) -> None:
    """OSの既定アプリでファイルを開く。"""
    import os
    import subprocess
    import sys

    if not path.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
