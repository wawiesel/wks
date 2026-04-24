from pydantic import BaseModel


class CatConfig(BaseModel):
    default_engine: str
    mime_engines: dict[str, str] | None = None
