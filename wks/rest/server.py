"""FastAPI app for read-mostly WKS services."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from wks.services import WKSService
from wks.services._models import FailureKind, ServiceResponse
from wks.services.cat import CatResponse
from wks.services.config import ConfigSectionResponse, ConfigSectionsResponse
from wks.services.search import SearchResponse
from wks.services.status import StatusResponse


def create_app(*, service: WKSService | None = None) -> FastAPI:
    """Create the REST application."""
    app = FastAPI(title="WKS REST", version="0.12.0")
    facade = service or WKSService.from_config()

    @app.get("/status", response_model=StatusResponse)
    def get_status() -> StatusResponse:
        return facade.status()

    @app.get("/search", response_model=SearchResponse)
    def search(
        query: str = "",
        index: str = "",
        k: int = Query(default=10, ge=1),
        query_image: str = "",
        strategy: str = "",
    ) -> SearchResponse:
        response = facade.search(query=query, index=index, k=k, query_image=query_image, strategy=strategy)
        return _raise_for_failure(response)

    @app.get("/cat", response_model=CatResponse)
    def cat(target: str, output_path: str | None = None, engine: str | None = None) -> CatResponse:
        response = facade.cat(target=target, output_path=output_path, engine=engine)
        return _raise_for_failure(response)

    @app.get("/config/sections", response_model=ConfigSectionsResponse)
    def config_sections() -> ConfigSectionsResponse:
        return facade.config_sections()

    @app.get("/config/{section}", response_model=ConfigSectionResponse)
    def config_section(section: str) -> ConfigSectionResponse:
        response = facade.config_section(section)
        return _raise_for_failure(response)

    return app


def _raise_for_failure(response: ServiceResponse):
    """Convert a failed service response into an HTTP error."""
    if response.success:
        return response
    raise HTTPException(
        status_code=_status_code_for_failure(response.failure_kind), detail=response.model_dump(mode="python")
    )


def _status_code_for_failure(failure_kind: FailureKind | None) -> int:
    """Map a service failure kind to an HTTP status code."""
    if failure_kind == "validation":
        return 400
    if failure_kind == "not_found":
        return 404
    if failure_kind == "conflict":
        return 409
    return 500
