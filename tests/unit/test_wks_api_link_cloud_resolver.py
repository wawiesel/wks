from pathlib import Path

from wks.api.config.CloudConfig import CloudConfig, CloudMapping
from wks.api.link.cloud_resolver import resolve_cloud_url


def test_resolve_cloud_url_onedrive(tmp_path):
    onedrive_root = tmp_path / "OneDrive - Corp"
    onedrive_root.mkdir()

    file_in_onedrive = onedrive_root / "Project" / "Doc.md"
    file_in_onedrive.parent.mkdir()
    file_in_onedrive.touch()

    config = CloudConfig(
        mappings=[
            CloudMapping(
                local_path=str(onedrive_root), remote_url="https://corp.sharepoint.com/sites/site/Shared Documents"
            )
        ]
    )

    url = resolve_cloud_url(file_in_onedrive, config)
    # Note: On Windows backslashes might appear in string generic logic,
    # but tmp_path is posix-like in most pytest envs or Path handles it.
    # Our implementation forces "/" replacements.
    assert url == "https://corp.sharepoint.com/sites/site/Shared Documents/Project/Doc.md"


def test_resolve_cloud_url_symlink(tmp_path):
    # Real location
    onedrive_root = tmp_path / "OneDrive - Real"
    onedrive_root.mkdir()
    real_file = onedrive_root / "file.txt"
    real_file.touch()

    # Symlink location
    symlink_dir = tmp_path / "MyProject"
    symlink_dir.mkdir()
    symlink_file = symlink_dir / "link_to_file.txt"
    symlink_file.symlink_to(real_file)

    config = CloudConfig(mappings=[CloudMapping(local_path=str(onedrive_root), remote_url="https://cloud.com/files")])

    url = resolve_cloud_url(symlink_file, config)
    assert url == "https://cloud.com/files/file.txt"


def test_resolve_cloud_url_directory_symlink(tmp_path):
    # Real location
    onedrive_root = tmp_path / "OneDrive - Real"
    onedrive_root.mkdir()
    real_subdir = onedrive_root / "SubDir"
    real_subdir.mkdir()
    real_file = real_subdir / "file.txt"
    real_file.touch()

    # Symlink location
    symlink_dir = tmp_path / "MyProject"
    symlink_dir.mkdir()
    symlink_subdir = symlink_dir / "LinkedDir"
    symlink_subdir.symlink_to(real_subdir)

    # Access file via symlinked dir
    file_via_link = symlink_subdir / "file.txt"

    config = CloudConfig(mappings=[CloudMapping(local_path=str(onedrive_root), remote_url="https://cloud.com/files")])

    url = resolve_cloud_url(file_via_link, config)
    assert url == "https://cloud.com/files/SubDir/file.txt"


def test_resolve_cloud_url_no_match(tmp_path):
    file_path = tmp_path / "other.txt"
    file_path.touch()

    config = CloudConfig(mappings=[CloudMapping(local_path=str(tmp_path / "OD"), remote_url="http://x")])

    assert resolve_cloud_url(file_path, config) is None


def test_expand_user_in_config(tmp_path, monkeypatch):
    # Mock home
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    onedrive_root = tmp_path / "OneDrive"
    onedrive_root.mkdir()
    file_path = onedrive_root / "test.txt"
    file_path.touch()

    config = CloudConfig(mappings=[CloudMapping(local_path="~/OneDrive", remote_url="https://cloud.com")])

    # We can't easily mock expanduser for "~" unless we set HOME env var,
    # but Path.expanduser() usually respects HOME.
    monkeypatch.setenv("HOME", str(tmp_path))

    url = resolve_cloud_url(file_path, config)
    assert url == "https://cloud.com/test.txt"
