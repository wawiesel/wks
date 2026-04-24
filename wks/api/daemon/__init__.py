from wks.api.config.output_models import output_model

DaemonStatusOutput = output_model(
    "DaemonStatusOutput", "running", "pid", "restrict_dir", "log_path", "last_sync", "lock_path"
)
DaemonStartOutput = output_model("DaemonStartOutput", "message", "running")
DaemonStopOutput = output_model("DaemonStopOutput", "message", "stopped")
DaemonClearOutput = output_model("DaemonClearOutput", "cleared", "message")


__all__ = [
    "DaemonClearOutput",
    "DaemonStartOutput",
    "DaemonStatusOutput",
    "DaemonStopOutput",
]
