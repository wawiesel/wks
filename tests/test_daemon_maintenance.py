import time


def test_daemon_background_maintenance(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".wks").mkdir()
    monkeypatch.setenv("HOME", str(home))

    from wks import daemon as daemon_mod

    class DummyVault:
        def __init__(self, *args, **kwargs):
            self.active_files_max_rows = kwargs.get("active_files_max_rows", 50)

        def ensure_structure(self):
            pass

        def update_active_files(self, *args, **kwargs):
            pass

        def log_file_operation(self, *args, **kwargs):
            pass

        def update_link_on_move(self, *args, **kwargs):
            pass

        def update_vault_links_on_move(self, *args, **kwargs):
            pass

        def create_project_note(self, *args, **kwargs):
            pass

        def write_health_page(self, *args, **kwargs):
            pass

        def mark_reference_deleted(self, *args, **kwargs):
            pass

        def write_doc_text(self, *args, **kwargs):
            pass

    class DummyActivity:
        def __init__(self, *args, **kwargs):
            pass

        def record_event(self, *args, **kwargs):
            pass

        def refresh_angles_all(self):
            pass

        def get_top_active_files(self, *args, **kwargs):
            return []

    monkeypatch.setattr(daemon_mod, "ObsidianVault", DummyVault)

    class DummySimilarity:
        def __init__(self):
            self.audit_calls = 0
            self.closed = False

        def audit_documents(self, remove_missing=True, fix_missing_metadata=True):
            self.audit_calls += 1
            return {"removed": 0, "updated": 0}

        def close(self):
            self.closed = True

    daemon = daemon_mod.WKSDaemon(
        config={},
        vault_path=tmp_path / "vault",
        base_dir="WKS",
        obsidian_log_max_entries=10,
        obsidian_active_files_max_rows=5,
        obsidian_source_max_chars=10,
        obsidian_destination_max_chars=10,
        obsidian_docs_keep=3,
        monitor_paths=[tmp_path],
        maintenance_interval_secs=0.1,
    )

    sim = DummySimilarity()
    daemon.similarity = sim
    daemon._maintenance_interval_secs = 0.05

    daemon._start_maintenance_thread()
    try:
        time.sleep(0.15)
        assert sim.audit_calls >= 1
    finally:
        daemon._stop_maintenance_thread()
        daemon.stop()

    assert sim.closed
