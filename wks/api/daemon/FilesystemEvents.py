from dataclasses import dataclass, field


@dataclass
class FilesystemEvents:
    modified: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.modified or self.created or self.deleted or self.moved)

    def total_count(self) -> int:
        return len(self.modified) + len(self.created) + len(self.deleted) + len(self.moved)
