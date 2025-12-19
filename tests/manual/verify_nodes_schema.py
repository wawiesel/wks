import os
import tempfile
from pathlib import Path

import wks
from wks.api.config.WKSConfig import WKSConfig
from wks.api.database.Database import Database
from wks.api.monitor.cmd_remote_detect import cmd_remote_detect
from wks.api.monitor.cmd_sync import cmd_sync

print(f"DEBUG: wks package location: {wks.__file__}")


def verify_nodes_schema():
    # Setup temp environment
    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        wks_home = tmp_home / ".wks"
        wks_home.mkdir()

        # Point config to temp home
        os.environ["WKS_HOME"] = str(wks_home)

        # Create minimal valid config
        # Create fake OneDrive path first
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

        # Create directory
        od_path.mkdir()
        test_file = od_path / "MonitoredDoc.md"
        test_file.write_text("Some content", encoding="utf-8")

        # Detect Remote (monkeypatch)
        import wks.api.monitor.cmd_remote_detect as m_detect

        original_detect = m_detect.detect_remote_mappings
        m_detect.detect_remote_mappings = lambda home_dir=None: original_detect(home_dir=tmp_home)

        result = cmd_remote_detect()
        list(result.progress_callback(result))  # Execute

        # Debug explain_path
        from wks.api.monitor.explain_path import explain_path

        allowed, trace = explain_path(cfg.monitor, test_file)
        print(f"DEBUG: explain_path({test_file}) -> {allowed}, trace={trace}")

        # Sync Monitor
        print("\n--- Syncing Monitor ---")
        sync_res = cmd_sync(str(test_file))
        list(sync_res.progress_callback(sync_res))

        if sync_res.success:
            print("SUCCESS: Monitor sync passed.")
            print(f"Details: {sync_res.output}")
        else:
            print(f"FAIL: Monitor sync failed. {sync_res.result}")
            return

        # Verify Monitor DB Schema
        print("\n--- Verifying Nodes DB Schema ---")
        from wks.utils.uri_utils import path_to_uri

        uri = path_to_uri(test_file)

        # Monitor collection name is just "nodes"
        with Database(cfg.database, "nodes") as db:
            # We must search by local_uri now
            docs = list(db.find({"local_uri": uri}))
            if not docs:
                print(f"FAIL: No docs found for local_uri={uri}")
                # Debug: Dump all docs
                all_docs = list(db.find({}))
                print(f"All docs in DB: {all_docs}")
            else:
                doc = docs[0]
                print(f"Found document: {doc}")

                # Check 1: path should be gone
                if "path" in doc:
                    print("FAIL: 'path' field still exists!")
                else:
                    print("SUCCESS: 'path' field is gone.")

                # Check 2: local_uri exists
                if doc.get("local_uri") == uri:
                    print("SUCCESS: 'local_uri' is correct.")
                else:
                    print(f"FAIL: 'local_uri' mismatch: {doc.get('local_uri')}")

                # Check 3: remote_uri exists and is correct
                remote_uri = doc.get("remote_uri")
                print(f"remote_uri: {remote_uri}")
                if remote_uri and "testremote-my.sharepoint.com" in remote_uri:
                    print("SUCCESS: 'remote_uri' populated correctly.")
                else:
                    print("FAIL: 'remote_uri' missing or incorrect.")


if __name__ == "__main__":
    verify_nodes_schema()
