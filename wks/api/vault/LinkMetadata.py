from dataclasses import dataclass


@dataclass(frozen=True)
class LinkMetadata:
    target_uri: str
    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target_uri": self.target_uri,
            "status": self.status,
        }
