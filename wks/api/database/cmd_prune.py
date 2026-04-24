from collections.abc import Iterator
from importlib import import_module
from typing import Any

from ..config.StageResult import StageResult
from . import DatabasePruneOutput
from .Database import Database

DB_HANDLERS = {
    "nodes": "wks.api.monitor.prune",
    "edges": "wks.api.link.prune",
    "transform": "wks.api.transform.prune",
}


def cmd_prune(database: str, remote: bool = False) -> StageResult:
    def do_work(result_obj: StageResult) -> Iterator[tuple[float, str]]:
        from ..config.WKSConfig import WKSConfig

        yield (0.1, "Loading configuration...")
        config: Any = WKSConfig.load()

        if database == "all":
            all_dbs = Database.list_databases(config.database)
            targets = [db for db in all_dbs if db in DB_HANDLERS]
        else:
            if database not in DB_HANDLERS:
                yield (1.0, "Complete")
                result_obj.output = DatabasePruneOutput(
                    errors=[f"No prune handler for database '{database}'. Known: {', '.join(sorted(DB_HANDLERS))}"],
                    warnings=[],
                    database=database,
                    deleted_count=0,
                    checked_count=0,
                ).model_dump(mode="python")
                result_obj.result = f"No prune handler for database '{database}'"
                result_obj.success = False
                return
            targets = [database]

        total_deleted = 0
        total_checked = 0
        all_warnings: list[str] = []

        total_targets = len(targets)
        for i, target_db in enumerate(targets):
            progress_base = 0.2 + (0.7 * (i / max(1, total_targets)))
            yield (progress_base, f"Pruning {target_db}...")

            progress_base = 0.2 + (0.7 * (i / max(1, total_targets)))
            yield (progress_base, f"Pruning {target_db}...")

            handler_module_name = DB_HANDLERS.get(target_db)
            if not handler_module_name:
                all_warnings.append(f"No prune handler found for database: {target_db}")
                continue

            try:
                module = import_module(handler_module_name)
                result = module.prune(config, remote=remote)

                deleted = result["deleted_count"]
                checked = result["checked_count"]
                warnings = result["warnings"]

                total_deleted += deleted
                total_checked += checked
                all_warnings.extend(warnings)

                from ._set_last_prune_timestamp import _set_last_prune_timestamp

                _set_last_prune_timestamp(target_db)

            except ImportError:
                all_warnings.append(f"Failed to import handler {handler_module_name} for {target_db}")
            except Exception as e:
                all_warnings.append(f"Failed to prune {target_db}: {e}")

        yield (1.0, "Complete")

        result_obj.output = DatabasePruneOutput(
            errors=[],
            warnings=all_warnings,
            database=database,
            deleted_count=total_deleted,
            checked_count=total_checked,
        ).model_dump(mode="python")

        result_obj.result = f"Pruned {database}: Checked {total_checked}, Deleted {total_deleted}"
        result_obj.success = True

    return StageResult(
        announce=f"Pruning {database}...",
        progress_callback=do_work,
    )
