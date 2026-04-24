import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import check_mongod_available, get_mongo_connection_info


def _find_wksc_command():
    project_root = Path(__file__).parents[2]
    venv_wksc = project_root / "venv" / "bin" / "wksc"
    if venv_wksc.exists():
        return str(venv_wksc)

    wksc_path = shutil.which("wksc")
    if wksc_path:
        return wksc_path

    raise RuntimeError("wksc command not found. Please install the package: pip install -e .")


def _get_wks_mcp_cmd():
    return [_find_wksc_command(), "mcp", "run", "--direct"]


def _require_mongod() -> None:
    if not check_mongod_available():
        pytest.fail("MCP smoke tests require `mongod` in PATH. Install MongoDB so `mongod --version` works.")


@pytest.fixture(scope="module")
def mcp_process(tmp_path_factory):
    _require_mongod()

    env_dir = tmp_path_factory.mktemp("mcp_env")
    home_dir = env_dir / "home"
    home_dir.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env["WKS_HOME"] = str(home_dir / ".wks")

    real_home = Path(os.environ["HOME"])
    if (real_home / ".local").exists():
        (home_dir / ".local").symlink_to(real_home / ".local")

    (home_dir / ".wks").mkdir()
    from tests.conftest import minimal_config_dict

    config = minimal_config_dict()

    mongo_uri, _, is_local = get_mongo_connection_info(home_dir)

    config["database"] = {
        "type": "mongo",
        "prefix": "wks_mcp_smoke",
        "data": {
            "uri": mongo_uri,
            "local": is_local,
        },
    }
    cache_dir = home_dir / "transform_cache"
    config["transform"]["cache"]["base_dir"] = str(cache_dir)
    config["monitor"]["filter"]["include_paths"] = [str(home_dir), str(cache_dir)]

    (home_dir / ".wks" / "config.json").write_text(json.dumps(config), encoding="utf-8")

    cmd = _get_wks_mcp_cmd()
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=0,  # Unbuffered
    )

    yield process

    process.terminate()
    process.wait()


def send_request(process, method, params=None, req_id=1):
    request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}

    try:
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
    except (BrokenPipeError, ValueError):
        try:
            _, errs = process.communicate(timeout=1)
            err = errs if errs else ""
        except Exception:
            err = "Could not retrieve stderr."
        raise AssertionError(f"MCP process died unexpectedly when sending request. STDERR:\n{err}") from None

    line = process.stdout.readline()
    if not line:
        try:
            rc = process.poll()
        except Exception:
            rc = None
        try:
            _, err_full = process.communicate(timeout=1)
            err = err_full if err_full else ""
        except Exception:
            err = ""
        raise AssertionError(f"No response from MCP process (returncode={rc}). STDERR:\n{err}")

    return json.loads(line)


def test_mcp_initialize(mcp_process):
    response = send_request(mcp_process, "initialize")
    assert response["result"]["serverInfo"]["name"] == "wks-mcp-server"


def test_mcp_list_tools(mcp_process):
    response = send_request(mcp_process, "tools/list", req_id=2)
    tools = response["result"]["tools"]
    assert any(t["name"] == "monitor_status" for t in tools)


def test_mcp_call_monitor_status(mcp_process):
    response = send_request(mcp_process, "tools/call", {"name": "monitor_status", "arguments": {}}, req_id=3)

    content = json.loads(response["result"]["content"][0]["text"])
    assert "data" in content
    assert "tracked_files" in content["data"]


def test_mcp_call_monitor_check(mcp_process):
    response = send_request(
        mcp_process,
        "tools/call",
        {"name": "monitor_check", "arguments": {"path": str(Path.home())}},
        req_id=4,
    )

    content = json.loads(response["result"]["content"][0]["text"])
    assert "data" in content
    assert "is_monitored" in content["data"]


def test_cli_mcp_list(wksc):
    result = wksc(["mcp", "list"])
    assert "targets" in result.stdout
