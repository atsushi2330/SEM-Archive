from __future__ import annotations

import sqlite3
from pathlib import Path

from sem_archive.db.schema import DEFAULT_SETTINGS, DEFAULT_TAG_CATEGORIES, SCHEMA_SQL
from sem_archive.models import AppSettings


def default_data_dir() -> Path:
    base = Path.home() / "SEM-Archive"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_db_path() -> Path:
    return default_data_dir() / "sem_archive.db"


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @classmethod
    def default(cls) -> Database:
        return cls(default_db_path())

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def initialize(self) -> None:
        conn = self.connection
        conn.executescript(SCHEMA_SQL)
        self._migrate(conn)
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        for name in DEFAULT_TAG_CATEGORIES:
            conn.execute(
                "INSERT OR IGNORE INTO tag_categories(name, is_builtin) VALUES (?, 1)",
                (name,),
            )
        conn.commit()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(folders)").fetchall()}
        additions = [
            ("substrate", "TEXT NOT NULL DEFAULT ''"),
            ("lot_name", "TEXT NOT NULL DEFAULT ''"),
            ("lot_id", "TEXT NOT NULL DEFAULT ''"),
            ("process", "TEXT NOT NULL DEFAULT ''"),
        ]
        for name, decl in additions:
            if name not in cols:
                conn.execute(f"ALTER TABLE folders ADD COLUMN {name} {decl}")

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get_settings(self) -> AppSettings:
        rows = self.connection.execute("SELECT key, value FROM app_settings").fetchall()
        data = {row["key"]: row["value"] for row in rows}
        return AppSettings(
            server_root=data.get("server_root", ""),
            local_root=data.get("local_root", ""),
            images_per_row=int(data.get("images_per_row", "10") or 10),
            image_extensions=data.get("image_extensions", ".jpg,.jpeg,.png,.tif,.tiff"),
            export_page_mode=data.get("export_page_mode", "slot"),
            export_row_mode=data.get("export_row_mode", "subdir"),
        )

    def save_settings(self, settings: AppSettings) -> None:
        pairs = {
            "server_root": settings.server_root,
            "local_root": settings.local_root,
            "images_per_row": str(settings.images_per_row),
            "image_extensions": settings.image_extensions,
            "export_page_mode": settings.export_page_mode,
            "export_row_mode": settings.export_row_mode,
        }
        for key, value in pairs.items():
            self.connection.execute(
                "INSERT INTO app_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        self.connection.commit()

    def reopen(self, db_path: Path) -> None:
        self.close()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
