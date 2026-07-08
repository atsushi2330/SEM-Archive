from __future__ import annotations

import sqlite3
from dataclasses import replace

from sem_archive.models import FolderRecord, Lot, SearchFilters, SemCase, Tag, TagCategory


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---- SEM cases ----
    def upsert_sem_case(self, case: SemCase) -> SemCase:
        existing = self.get_sem_by_request_no(case.request_no)
        if existing:
            self.conn.execute(
                """
                UPDATE sem_cases
                SET memo = ?, condition = ?, local_path = ?, imported_at = ?
                WHERE id = ?
                """,
                (case.memo, case.condition, case.local_path, case.imported_at, existing.id),
            )
            self.conn.commit()
            return replace(existing, memo=case.memo, condition=case.condition,
                           local_path=case.local_path, imported_at=case.imported_at)
        cur = self.conn.execute(
            """
            INSERT INTO sem_cases(request_no, memo, condition, local_path, imported_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (case.request_no, case.memo, case.condition, case.local_path, case.imported_at),
        )
        self.conn.commit()
        return replace(case, id=cur.lastrowid)

    def get_sem_by_request_no(self, request_no: str) -> SemCase | None:
        row = self.conn.execute(
            "SELECT * FROM sem_cases WHERE request_no = ?",
            (request_no,),
        ).fetchone()
        return self._row_to_sem(row) if row else None

    def get_sem(self, sem_id: int) -> SemCase | None:
        row = self.conn.execute("SELECT * FROM sem_cases WHERE id = ?", (sem_id,)).fetchone()
        return self._row_to_sem(row) if row else None

    def list_sem_cases(self) -> list[SemCase]:
        rows = self.conn.execute(
            "SELECT * FROM sem_cases ORDER BY imported_at DESC, request_no DESC"
        ).fetchall()
        return [self._row_to_sem(r) for r in rows]

    def update_sem_meta(self, sem_id: int, memo: str, condition: str) -> None:
        self.conn.execute(
            "UPDATE sem_cases SET memo = ?, condition = ? WHERE id = ?",
            (memo, condition, sem_id),
        )
        self.conn.commit()

    def search_sem_cases(self, filters: SearchFilters) -> list[SemCase]:
        sql = """
            SELECT DISTINCT s.*
            FROM sem_cases s
            LEFT JOIN lots l ON l.sem_case_id = s.id
            LEFT JOIN folders f ON f.sem_case_id = s.id
            LEFT JOIN taggings ts ON ts.target_type = 'sem' AND ts.target_id = s.id
            LEFT JOIN taggings tf ON tf.target_type = 'folder' AND tf.target_id = f.id
            WHERE 1=1
        """
        params: list[object] = []
        q = filters.query.strip()
        if q:
            like = f"%{q}%"
            sql += """
                AND (
                    s.request_no LIKE ?
                    OR s.memo LIKE ?
                    OR s.condition LIKE ?
                    OR f.memo LIKE ?
                    OR f.condition LIKE ?
                    OR f.slot_id LIKE ?
                    OR l.lot_no LIKE ?
                )
            """
            params.extend([like] * 7)
        if filters.lot_no.strip():
            sql += " AND l.lot_no LIKE ?"
            params.append(f"%{filters.lot_no.strip()}%")
        if filters.slot_id.strip():
            sql += " AND f.slot_id LIKE ?"
            params.append(f"%{filters.slot_id.strip()}%")
        if filters.tag_ids:
            placeholders = ",".join("?" for _ in filters.tag_ids)
            sql += f"""
                AND (
                    ts.tag_id IN ({placeholders})
                    OR tf.tag_id IN ({placeholders})
                )
            """
            params.extend(filters.tag_ids)
            params.extend(filters.tag_ids)
        sql += " ORDER BY s.imported_at DESC, s.request_no DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_sem(r) for r in rows]

    # ---- Lots ----
    def set_lots(self, sem_case_id: int, lot_nos: list[str]) -> None:
        self.conn.execute("DELETE FROM lots WHERE sem_case_id = ?", (sem_case_id,))
        for lot_no in lot_nos:
            value = lot_no.strip()
            if not value:
                continue
            self.conn.execute(
                "INSERT OR IGNORE INTO lots(sem_case_id, lot_no) VALUES (?, ?)",
                (sem_case_id, value),
            )
        self.conn.commit()

    def list_lots(self, sem_case_id: int) -> list[Lot]:
        rows = self.conn.execute(
            "SELECT * FROM lots WHERE sem_case_id = ? ORDER BY lot_no",
            (sem_case_id,),
        ).fetchall()
        return [
            Lot(id=r["id"], sem_case_id=r["sem_case_id"], lot_no=r["lot_no"]) for r in rows
        ]

    # ---- Folders ----
    def replace_folders(self, sem_case_id: int, folders: list[FolderRecord]) -> list[FolderRecord]:
        # 既存メタを引き継ぐために relative_path マップを取得
        old_rows = self.conn.execute(
            """
            SELECT relative_path, memo, condition, slot_id, is_slot,
                   substrate, lot_name, lot_id, process
            FROM folders WHERE sem_case_id = ?
            """,
            (sem_case_id,),
        ).fetchall()
        old_map = {r["relative_path"]: r for r in old_rows}
        self.conn.execute("DELETE FROM folders WHERE sem_case_id = ?", (sem_case_id,))

        path_to_id: dict[str, int] = {}
        result: list[FolderRecord] = []
        for folder in sorted(folders, key=lambda f: f.relative_path.count("/")):
            old = old_map.get(folder.relative_path)
            memo = old["memo"] if old else folder.memo
            condition = old["condition"] if old else folder.condition
            substrate = old["substrate"] if old else folder.substrate
            lot_name = old["lot_name"] if old else folder.lot_name
            lot_id = old["lot_id"] if old else folder.lot_id
            process = old["process"] if old else folder.process
            slot_id = folder.slot_id
            is_slot = int(folder.is_slot)
            if old and old["slot_id"] and not folder.slot_id:
                slot_id = old["slot_id"]
                is_slot = int(old["is_slot"])
            if folder.relative_path and "/" in folder.relative_path:
                parent_rel = folder.relative_path.rsplit("/", 1)[0]
                parent_id = path_to_id.get(parent_rel)
            else:
                parent_id = None
            cur = self.conn.execute(
                """
                INSERT INTO folders(
                    sem_case_id, parent_id, relative_path, folder_name,
                    slot_id, memo, condition, substrate, lot_name, lot_id, process, is_slot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sem_case_id,
                    parent_id,
                    folder.relative_path,
                    folder.folder_name,
                    slot_id,
                    memo,
                    condition,
                    substrate,
                    lot_name,
                    lot_id,
                    process,
                    is_slot,
                ),
            )
            path_to_id[folder.relative_path] = int(cur.lastrowid)
            result.append(
                FolderRecord(
                    id=int(cur.lastrowid),
                    sem_case_id=sem_case_id,
                    relative_path=folder.relative_path,
                    folder_name=folder.folder_name,
                    parent_id=parent_id,
                    slot_id=slot_id,
                    memo=memo,
                    condition=condition,
                    substrate=substrate,
                    lot_name=lot_name,
                    lot_id=lot_id,
                    process=process,
                    is_slot=bool(is_slot),
                )
            )
        self.conn.commit()
        return result

    def list_folders(self, sem_case_id: int) -> list[FolderRecord]:
        rows = self.conn.execute(
            "SELECT * FROM folders WHERE sem_case_id = ? ORDER BY relative_path",
            (sem_case_id,),
        ).fetchall()
        return [self._row_to_folder(r) for r in rows]

    def list_all_folders(self) -> list[tuple[SemCase, FolderRecord]]:
        rows = self.conn.execute(
            """
            SELECT f.*, s.request_no, s.memo AS sem_memo, s.condition AS sem_condition,
                   s.local_path, s.imported_at
            FROM folders f
            JOIN sem_cases s ON s.id = f.sem_case_id
            ORDER BY s.request_no, f.relative_path
            """
        ).fetchall()
        result: list[tuple[SemCase, FolderRecord]] = []
        for r in rows:
            sem = SemCase(
                id=r["sem_case_id"],
                request_no=r["request_no"],
                memo=r["sem_memo"],
                condition=r["sem_condition"],
                local_path=r["local_path"],
                imported_at=r["imported_at"],
            )
            result.append((sem, self._row_to_folder(r)))
        return result

    def get_folder(self, folder_id: int) -> FolderRecord | None:
        row = self.conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        return self._row_to_folder(row) if row else None

    def update_folder_meta(
        self,
        folder_id: int,
        memo: str | None = None,
        condition: str | None = None,
        slot_id: str | None = None,
        is_slot: bool | None = None,
        substrate: str | None = None,
        lot_name: str | None = None,
        lot_id: str | None = None,
        process: str | None = None,
    ) -> None:
        folder = self.get_folder(folder_id)
        if not folder:
            return
        new_memo = folder.memo if memo is None else memo
        new_condition = folder.condition if condition is None else condition
        new_slot = folder.slot_id if slot_id is None else (slot_id or None)
        new_is_slot = folder.is_slot if is_slot is None else is_slot
        new_substrate = folder.substrate if substrate is None else substrate
        new_lot_name = folder.lot_name if lot_name is None else lot_name
        new_lot_id = folder.lot_id if lot_id is None else lot_id
        new_process = folder.process if process is None else process
        self.conn.execute(
            """
            UPDATE folders
            SET memo = ?, condition = ?, slot_id = ?, is_slot = ?,
                substrate = ?, lot_name = ?, lot_id = ?, process = ?
            WHERE id = ?
            """,
            (
                new_memo,
                new_condition,
                new_slot,
                int(new_is_slot),
                new_substrate,
                new_lot_name,
                new_lot_id,
                new_process,
                folder_id,
            ),
        )
        self.conn.commit()

    def update_folder_field(self, folder_id: int, field: str, value: str) -> None:
        allowed = {
            "memo",
            "condition",
            "slot_id",
            "substrate",
            "lot_name",
            "lot_id",
            "process",
        }
        if field not in allowed:
            raise ValueError(f"unsupported field: {field}")
        if field == "slot_id":
            slot = value.strip() or None
            self.conn.execute(
                "UPDATE folders SET slot_id = ?, is_slot = ? WHERE id = ?",
                (slot, int(bool(slot)), folder_id),
            )
        else:
            self.conn.execute(
                f"UPDATE folders SET {field} = ? WHERE id = ?",
                (value, folder_id),
            )
        self.conn.commit()

    # ---- Tags ----
    def list_categories(self) -> list[TagCategory]:
        rows = self.conn.execute(
            "SELECT * FROM tag_categories ORDER BY is_builtin DESC, name"
        ).fetchall()
        return [
            TagCategory(id=r["id"], name=r["name"], is_builtin=bool(r["is_builtin"]))
            for r in rows
        ]

    def add_category(self, name: str) -> TagCategory:
        cur = self.conn.execute(
            "INSERT INTO tag_categories(name, is_builtin) VALUES (?, 0)",
            (name.strip(),),
        )
        self.conn.commit()
        return TagCategory(id=cur.lastrowid, name=name.strip(), is_builtin=False)

    def list_tags(self) -> list[Tag]:
        rows = self.conn.execute(
            """
            SELECT t.*, c.name AS category_name
            FROM tags t
            JOIN tag_categories c ON c.id = t.category_id
            ORDER BY c.name, t.name
            """
        ).fetchall()
        return [
            Tag(
                id=r["id"],
                category_id=r["category_id"],
                name=r["name"],
                category_name=r["category_name"],
            )
            for r in rows
        ]

    def add_tag(self, category_id: int, name: str) -> Tag:
        cur = self.conn.execute(
            "INSERT INTO tags(category_id, name) VALUES (?, ?)",
            (category_id, name.strip()),
        )
        self.conn.commit()
        cat = self.conn.execute(
            "SELECT name FROM tag_categories WHERE id = ?", (category_id,)
        ).fetchone()
        return Tag(
            id=cur.lastrowid,
            category_id=category_id,
            name=name.strip(),
            category_name=cat["name"] if cat else "",
        )

    def set_target_tags(self, target_type: str, target_id: int, tag_ids: list[int]) -> None:
        self.conn.execute(
            "DELETE FROM taggings WHERE target_type = ? AND target_id = ?",
            (target_type, target_id),
        )
        for tag_id in tag_ids:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO taggings(tag_id, target_type, target_id)
                VALUES (?, ?, ?)
                """,
                (tag_id, target_type, target_id),
            )
        self.conn.commit()

    def list_target_tag_ids(self, target_type: str, target_id: int) -> list[int]:
        rows = self.conn.execute(
            "SELECT tag_id FROM taggings WHERE target_type = ? AND target_id = ?",
            (target_type, target_id),
        ).fetchall()
        return [int(r["tag_id"]) for r in rows]

    def list_target_tags(self, target_type: str, target_id: int) -> list[Tag]:
        rows = self.conn.execute(
            """
            SELECT t.*, c.name AS category_name
            FROM tags t
            JOIN tag_categories c ON c.id = t.category_id
            JOIN taggings g ON g.tag_id = t.id
            WHERE g.target_type = ? AND g.target_id = ?
            ORDER BY c.name, t.name
            """,
            (target_type, target_id),
        ).fetchall()
        return [
            Tag(
                id=r["id"],
                category_id=r["category_id"],
                name=r["name"],
                category_name=r["category_name"],
            )
            for r in rows
        ]

    @staticmethod
    def _row_to_sem(row: sqlite3.Row) -> SemCase:
        return SemCase(
            id=row["id"],
            request_no=row["request_no"],
            memo=row["memo"],
            condition=row["condition"],
            local_path=row["local_path"],
            imported_at=row["imported_at"],
        )

    @staticmethod
    def _row_to_folder(row: sqlite3.Row) -> FolderRecord:
        keys = set(row.keys())
        return FolderRecord(
            id=row["id"],
            sem_case_id=row["sem_case_id"],
            parent_id=row["parent_id"],
            relative_path=row["relative_path"],
            folder_name=row["folder_name"],
            slot_id=row["slot_id"],
            memo=row["memo"],
            condition=row["condition"],
            substrate=row["substrate"] if "substrate" in keys else "",
            lot_name=row["lot_name"] if "lot_name" in keys else "",
            lot_id=row["lot_id"] if "lot_id" in keys else "",
            process=row["process"] if "process" in keys else "",
            is_slot=bool(row["is_slot"]),
        )

