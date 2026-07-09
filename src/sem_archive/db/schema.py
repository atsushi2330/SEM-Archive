from __future__ import annotations

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sem_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_no TEXT NOT NULL UNIQUE,
    memo TEXT NOT NULL DEFAULT '',
    condition TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sem_case_id INTEGER NOT NULL REFERENCES sem_cases(id) ON DELETE CASCADE,
    lot_no TEXT NOT NULL,
    UNIQUE(sem_case_id, lot_no)
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sem_case_id INTEGER NOT NULL REFERENCES sem_cases(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    folder_name TEXT NOT NULL,
    slot_id TEXT,
    memo TEXT NOT NULL DEFAULT '',
    condition TEXT NOT NULL DEFAULT '',
    substrate TEXT NOT NULL DEFAULT '',
    lot_name TEXT NOT NULL DEFAULT '',
    lot_id TEXT NOT NULL DEFAULT '',
    process TEXT NOT NULL DEFAULT '',
    is_slot INTEGER NOT NULL DEFAULT 0,
    UNIQUE(sem_case_id, relative_path)
);

CREATE TABLE IF NOT EXISTS tag_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_builtin INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES tag_categories(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE(category_id, name)
);

CREATE TABLE IF NOT EXISTS taggings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK(target_type IN ('sem', 'folder')),
    target_id INTEGER NOT NULL,
    UNIQUE(tag_id, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_folders_sem ON folders(sem_case_id);
CREATE INDEX IF NOT EXISTS idx_lots_sem ON lots(sem_case_id);
CREATE INDEX IF NOT EXISTS idx_taggings_target ON taggings(target_type, target_id);
"""

DEFAULT_TAG_CATEGORIES = ("下地", "工程", "評価内容")

DEFAULT_SETTINGS = {
    "server_root": "",
    "local_root": "",
    "images_per_row": "10",
    "image_extensions": ".jpg,.jpeg,.png,.tif,.tiff",
    "export_page_mode": "slot",
    "export_row_mode": "subdir",
    "theme_id": "default",
}
