import os
import tempfile
from pathlib import Path

import wks
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.link.cmd_show import cmd_show
from wks.api.link.cmd_sync import cmd_sync as link_sync
from wks.api.monitor.cmd_remote_detect import cmd_remote_detect

print(f"DEBUG: wks package location: {wks.__file__}")


def verify_edges_schema():
    # Setup temp environment
    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        wks_home = tmp_home / ".wks"
        wks_home.mkdir()

        # Point config to temp home
        os.environ["WKS_HOME"] = str(wks_home)

        # Create fake OneDrive path
        od_path = (tmp_home / "OneDrive - TestRemote").resolve()

        config_data = {
            "monitor": {
                "filter": {
                    "include_paths": [str(od_path)],
                    "exclude_paths": [],
                    "include_dirnames": [],
                    "exclude_dirnames": [],
                    "include_globs": [],
                    "exclude_globs": [],
                },
                "priority": {
                    "dirs": {str(od_path): 10.0},
                    "weights": {
                        "depth_multiplier": 1.0,
                        "underscore_multiplier": 0.5,
                        "only_underscore_multiplier": 0.1,
                        "extension_weights": {},
                    },
                },
                "max_documents": 1000,
                "min_priority": 0.0,
                "remote": {"mappings": []},
            },
            "database": {
                "type": "mongo",
                "prefix": "wks",
                "data": {"uri": "mongodb://localhost:27017/wks_test", "local": False},
            },
            "service": {
                "type": "darwin",
                "data": {"label": "com.wks.daemon", "keep_alive": False, "run_at_load": False},
            },
            "daemon": {"enabled": False, "sync_interval_secs": 60},
            "vault": {"type": "obsidian", "base_dir": str(tmp_home / "Vault")},
        }

        cfg = WKSConfig(**config_data)  # type: ignore
        cfg.save()

        # Clean DB
        with Database(cfg.database, "nodes") as db:
            db.delete_many({})
        with Database(cfg.database, "edges") as db:
            db.delete_many({})

        # Create directory and file with links
        od_path.mkdir()
        source_file = od_path / "SourceDoc.md"
        target_file = od_path / "TargetDoc.md"

        target_file.write_text("Target content", encoding="utf-8")
        # Link from source to target
        source_file.write_text(f"Link to [target]({target_file.name})", encoding="utf-8")

        # Detect Remote (monkeypatch)
        import wks.api.monitor.cmd_remote_detect as m_detect

        original_detect = m_detect.detect_remote_mappings
        m_detect.detect_remote_mappings = lambda home_dir=None: original_detect(home_dir=tmp_home)

        detect_res = cmd_remote_detect()
        list(detect_res.progress_callback(detect_res))

        # Reload config to get remote mappings
        # (Assuming cmd_remote_detect saves config)

        # Sync Link
        print("\n--- Syncing Link ---")
        sync_res = link_sync(str(source_file), remote=True)
        list(sync_res.progress_callback(sync_res))

        if sync_res.success:
            print("SUCCESS: Link sync passed.")
            print(f"Details: {sync_res.output}")
        else:
            print(f"FAIL: Link sync failed. {sync_res.result}")
            return

        # Verify Link DB Schema
        print("\n--- Verifying Edges DB Schema ---")
        from wks.utils.uri_utils import path_to_uri

        source_uri = path_to_uri(source_file)

        with Database(cfg.database, "edges") as db:
            docs = list(db.find({"from_local_uri": source_uri}))
            if not docs:
                print(f"FAIL: No docs found for from_local_uri={source_uri}")
                print(f"All docs: {list(db.find({}))}")
            else:
                doc = docs[0]
                print(f"Found document: {doc}")

                # Check fields
                issues = []
                if "from_uri" in doc:
                    issues.append("'from_uri' still exists")
                if "to_uri" in doc:
                    issues.append("'to_uri' still exists")

                if "from_local_uri" not in doc:
                    issues.append("'from_local_uri' missing")
                if "to_local_uri" not in doc:
                    issues.append("'to_local_uri' missing")

                if "from_remote_uri" not in doc:
                    issues.append("'from_remote_uri' missing")
                elif not doc["from_remote_uri"]:
                    issues.append("'from_remote_uri' empty")

                if "to_remote_uri" not in doc:
                    issues.append("'to_remote_uri' missing")
                # Check logic: we requested remote=True, target is in seeded remote dir
                elif not doc["to_remote_uri"]:
                    issues.append("'to_remote_uri' empty")

                if issues:
                    print(f"FAIL: Schema issues: {issues}")
                else:
                    print("SUCCESS: Link schema is correct and populated.")

        # Verify cmd_show compatibility
        print("\n--- Verifying cmd_show ---")
        show_res = cmd_show(source_uri, direction="from")
        list(show_res.progress_callback(show_res))

        if show_res.success and show_res.output["links"]:
            print("SUCCESS: cmd_show returned links.")
            print(f"Show Output: {show_res.output}")
        else:
            print(f"FAIL: cmd_show failed or no links. {show_res.result}")


if __name__ == "__main__":
    verify_edges_schema()
