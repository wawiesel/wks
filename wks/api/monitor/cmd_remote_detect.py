"""Remote detection command."""

from collections.abc import Iterator
from typing import Any

from wks.api.config.WKSConfig import WKSConfig
from wks.api.monitor.detect_remote_mappings import detect_remote_mappings
from wks.api.StageResult import StageResult


def cmd_remote_detect() -> StageResult:
    """Detect remote folders and update configuration."""

    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        yield (0.1, "Loading configuration...")
        config: WKSConfig = WKSConfig.load()
        remote_config = config.monitor.remote

        yield (0.3, "Detecting remote folders...")
        new_mappings = detect_remote_mappings()

        output_data: dict[str, Any] = {
            "mappings_detected": [],
            "previous_count": len(remote_config.mappings),
            "new_count": 0,
        }

        if not new_mappings:
            result_obj.result = "No remote folders detected."
            result_obj.success = True
            result_obj.output = output_data
            return

        mapped_count = 0
        existing_paths = {m.local_path for m in remote_config.mappings}

        for m in new_mappings:
            if m.local_path not in existing_paths:
                remote_config.mappings.append(m)
                output_data["mappings_detected"].append(m.model_dump())
                mapped_count += 1

        output_data["new_count"] = mapped_count

        if mapped_count > 0:
            yield (0.8, "Updating configuration...")
            config.save()
            result_obj.result = f"Detected and added {mapped_count} remote mappings."
        else:
            result_obj.result = "No new remote mappings found (duplicates skipped)."

        result_obj.success = True
        result_obj.output = output_data

    return StageResult(announce="Detecting remote folders...", progress_callback=do_work)
