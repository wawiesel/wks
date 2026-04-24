"""Link API domain."""

from wks.api.config.output_models import output_model

LinkCheckOutput = output_model("LinkCheckOutput", "path", "is_monitored", "links")
LinkShowOutput = output_model("LinkShowOutput", "uri", "direction", "links")
LinkStatusOutput = output_model("LinkStatusOutput", "total_links", "total_files")
LinkSyncOutput = output_model("LinkSyncOutput", "path", "is_monitored", "links_found", "links_synced")

__all__ = [
    "LinkCheckOutput",
    "LinkShowOutput",
    "LinkStatusOutput",
    "LinkSyncOutput",
]
