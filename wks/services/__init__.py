from __future__ import annotations

from pathlib import Path

from wks.api.config.WKSConfig import WKSConfig

from .cat import CatRequest, CatResponse, read_content
from .config import ConfigSectionResponse, ConfigSectionsResponse, list_config_sections, show_config_section
from .mv import MoveRequest, MoveResponse, move_document
from .search import SearchRequest, SearchResponse, search_documents
from .status import StatusResponse, collect_status


class WKSService:
    def __init__(self, *, config: WKSConfig | None = None):
        self._config = config

    @classmethod
    def from_config(cls, config: WKSConfig | None = None) -> WKSService:
        return cls(config=config or WKSConfig.load())

    def status(self) -> StatusResponse:
        return collect_status()

    def search(
        self,
        *,
        query: str = "",
        index: str = "",
        k: int = 10,
        query_image: str = "",
        strategy: str = "",
    ) -> SearchResponse:
        request = SearchRequest(query=query, index=index, k=k, query_image=query_image, strategy=strategy)
        return search_documents(request, config=self._config)

    def cat(self, *, target: str, output_path: str | Path | None = None, engine: str | None = None) -> CatResponse:
        request = CatRequest(target=target, output_path=Path(output_path) if output_path else None, engine=engine)
        return read_content(request, config=self._config)

    def mv(self, *, source: str, dest: str) -> MoveResponse:
        return move_document(MoveRequest(source=source, dest=dest), config=self._config)

    def config_sections(self) -> ConfigSectionsResponse:
        return list_config_sections(config=self._config)

    def config_section(self, section: str) -> ConfigSectionResponse:
        return show_config_section(section, config=self._config)


__all__ = [
    "CatRequest",
    "CatResponse",
    "ConfigSectionResponse",
    "ConfigSectionsResponse",
    "MoveRequest",
    "MoveResponse",
    "SearchRequest",
    "SearchResponse",
    "StatusResponse",
    "WKSService",
    "collect_status",
    "list_config_sections",
    "move_document",
    "read_content",
    "search_documents",
    "show_config_section",
]
