import pytest

from tests.unit.conftest import run_cmd, write_watched_file
from wks.api.config.URI import URI
from wks.api.transform.cmd_engine import cmd_engine
from wks.api.transform.get_content import get_content


@pytest.mark.transform
def test_get_content_file(wks_home, minimal_config_dict):
    """Test retrieving content for a file."""
    test_file = write_watched_file(wks_home, name="get_me.txt", content="Get Content")

    run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})

    content = get_content(str(test_file))
    assert content == "Get Content"


@pytest.mark.transform
def test_get_content_checksum(wks_home, minimal_config_dict):
    """Test retrieving content by checksum."""
    test_file = write_watched_file(wks_home, name="checksum_me.txt", content="Checksum Content")

    res = run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})
    assert res.success is True
    checksum = res.output["checksum"]

    content = get_content(checksum)
    assert content == "Checksum Content"


@pytest.mark.transform
def test_get_content_missing_checksum(wks_home, minimal_config_dict):
    """Test retrieving content for missing checksum."""
    with pytest.raises(ValueError) as excinfo:
        get_content("0000000000000000000000000000000000000000000000000000000000000000")
    assert "not found" in str(excinfo.value)


@pytest.mark.transform
def test_get_content_missing_file(wks_home, minimal_config_dict):
    """Test retrieving content for missing file path."""
    with pytest.raises(ValueError) as excinfo:
        get_content("/non/existent/path.txt")
    assert "not found" in str(excinfo.value)


@pytest.mark.transform
def test_get_content_to_output_file(wks_home, minimal_config_dict, tmp_path):
    """Test retrieving content and writing to output file."""
    test_file = write_watched_file(wks_home, name="output_me.txt", content="Output Content")
    run_cmd(cmd_engine, engine="textpass", uri=URI.from_path(test_file), overrides={})

    out_file = tmp_path / "out.md"
    get_content(str(test_file), output_path=out_file)
    assert out_file.exists()
    assert out_file.read_text() == "Output Content"
