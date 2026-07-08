from __future__ import annotations

import re

_SLOT_RE = re.compile(r"^(?:s|slot)?(\d+)$", re.IGNORECASE)


def detect_slot_id(folder_name: str) -> str | None:
    """フォルダ名から Slot ID を推定する。

    例: s1 / S1 / slot1 / Slot01 / 1 -> 正規化して返す。
    数字だけの場合も slot 候補として扱う。
    """
    name = folder_name.strip()
    if not name:
        return None
    match = _SLOT_RE.match(name)
    if not match:
        return None
    number = str(int(match.group(1)))
    # 元のプレフィックス感を残しつつ正規化: S{n}
    return f"S{number}"


def is_slot_folder(folder_name: str) -> bool:
    return detect_slot_id(folder_name) is not None
