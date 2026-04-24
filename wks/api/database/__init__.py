"""Database API module."""

from wks.api.config.output_models import output_model

DatabaseListOutput = output_model("DatabaseListOutput", "prefix", "databases")
DatabaseShowOutput = output_model("DatabaseShowOutput", "database", "query", "limit", "count", "results")
DatabaseResetOutput = output_model("DatabaseResetOutput", "database", "deleted_count")
DatabasePruneOutput = output_model("DatabasePruneOutput", "database", "deleted_count", "checked_count")


__all__ = [
    "DatabaseListOutput",
    "DatabasePruneOutput",
    "DatabaseResetOutput",
    "DatabaseShowOutput",
]
