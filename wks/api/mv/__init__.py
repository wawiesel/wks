"""Mv API module."""

from wks.api.config.output_models import output_model

MvMvOutput = output_model("MvMvOutput", "source", "destination", "database_updated", "success")

__all__ = ["MvMvOutput"]
