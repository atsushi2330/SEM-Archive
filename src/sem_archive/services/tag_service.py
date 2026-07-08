from __future__ import annotations

from sem_archive.db.repository import Repository
from sem_archive.models import Tag, TagCategory


class TagService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def categories(self) -> list[TagCategory]:
        return self.repo.list_categories()

    def tags(self) -> list[Tag]:
        return self.repo.list_tags()

    def add_category(self, name: str) -> TagCategory:
        return self.repo.add_category(name)

    def add_tag(self, category_id: int, name: str) -> Tag:
        return self.repo.add_tag(category_id, name)

    def get_tags_for(self, target_type: str, target_id: int) -> list[Tag]:
        return self.repo.list_target_tags(target_type, target_id)

    def set_tags_for(self, target_type: str, target_id: int, tag_ids: list[int]) -> None:
        self.repo.set_target_tags(target_type, target_id, tag_ids)
