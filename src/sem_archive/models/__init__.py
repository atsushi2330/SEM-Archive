from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppSettings:
    server_root: str = ""
    local_root: str = ""
    images_per_row: int = 10
    image_extensions: str = ".jpg,.jpeg,.png,.tif,.tiff"
    export_page_mode: str = "slot"  # slot | flat
    export_row_mode: str = "subdir"  # subdir | none
    ppt_label_under_image: bool = True
    theme_id: str = "default"

    def extension_set(self) -> set[str]:
        return {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in self.image_extensions.split(",")
            if ext.strip()
        }


@dataclass
class SemCase:
    id: int | None
    request_no: str
    memo: str = ""
    condition: str = ""
    local_path: str = ""
    imported_at: str = ""


@dataclass
class Lot:
    id: int | None
    sem_case_id: int
    lot_no: str


@dataclass
class FolderRecord:
    id: int | None
    sem_case_id: int
    relative_path: str
    folder_name: str
    parent_id: int | None = None
    slot_id: str | None = None
    memo: str = ""
    condition: str = ""
    substrate: str = ""
    lot_name: str = ""
    lot_id: str = ""
    process: str = ""
    is_slot: bool = False


@dataclass
class TagCategory:
    id: int | None
    name: str
    is_builtin: bool = False


@dataclass
class Tag:
    id: int | None
    category_id: int
    name: str
    category_name: str = ""


@dataclass
class SearchFilters:
    query: str = ""
    tag_ids: list[int] = field(default_factory=list)
    lot_no: str = ""
    slot_id: str = ""
