"""Tests for wks/display/service.py - Service status display helpers."""

from wks.api.display.service import build_status_rows, fmt_bool, format_timestamp
from wks.api.service.service_controller import ServiceStatusData, ServiceStatusLaunch


class TestFmtBool:
    """Tests for fmt_bool display function."""

    def test_true(self):
        assert fmt_bool(True) == "true"

    def test_false(self):
        assert fmt_bool(False) == "false"

    def test_none(self):
        assert fmt_bool(None) == "-"

    def test_true_color(self):
        assert fmt_bool(True, color=True) == "[green]true[/green]"

    def test_false_color(self):
        assert fmt_bool(False, color=True) == "[red]false[/red]"

    def test_none_color(self):
        assert fmt_bool(None, color=True) == "-"


class TestFormatTimestamp:
    """Tests for format_timestamp display function."""

    def test_none(self):
        assert format_timestamp(None, "%Y-%m-%d") == ""

    def test_empty_string(self):
        assert format_timestamp("", "%Y-%m-%d") == ""

    def test_iso_format_z(self):
        assert format_timestamp("2025-01-01T12:00:00Z", "%Y-%m-%d") == "2025-01-01"

    def test_iso_format_offset(self):
        assert format_timestamp("2025-01-01T12:00:00+00:00", "%Y-%m-%d") == "2025-01-01"

    def test_invalid_returns_original(self):
        assert format_timestamp("invalid", "%Y-%m-%d") == "invalid"

    def test_fallback_no_t_separator(self):
        # Test the fallback path where T is replaced with space
        assert format_timestamp("2025-01-01 12:00:00", "%Y-%m-%d") == "2025-01-01"

    def test_strftime_format(self):
        # strftime with valid format
        result = format_timestamp("2025-01-01T12:00:00Z", "%H:%M")
        assert result == "12:00"


class TestBuildStatusRows:
    """Tests for build_status_rows display function."""

    def test_basic_status(self):
        """Test basic status data produces expected rows."""
        status = ServiceStatusData(
            running=True,
            uptime="1h",
            pid=123,
            ok=True,
            lock=True,
        )
        rows = build_status_rows(status)

        # Should have Health and File System sections
        labels = [r[0] for r in rows]
        assert any("Health" in label for label in labels)
        assert any("File System" in label for label in labels)

        # Check specific values
        row_dict = {r[0].strip(): r[1] for r in rows}
        assert "[green]true[/green]" in row_dict.get("Running", "")
        assert row_dict.get("Uptime", "") == "1h"
        assert row_dict.get("PID", "") == "123"

    def test_with_launch_agent(self):
        """Test status with launch agent data."""
        status = ServiceStatusData(
            running=True,
            launch=ServiceStatusLaunch(
                state="running",
                program="/usr/bin/python3",
                stdout="/var/log/wks.out",
                stderr="/var/log/wks.err",
                path="/path/to/plist",
                type="LaunchAgent",
            ),
        )
        rows = build_status_rows(status)

        labels = [r[0] for r in rows]
        assert any("Launch" in label for label in labels)

        row_dict = {r[0].strip(): r[1] for r in rows}
        assert row_dict.get("Program", "") == "/usr/bin/python3"

    def test_without_launch_agent(self):
        """Test status without launch agent data."""
        status = ServiceStatusData(running=True)
        rows = build_status_rows(status)

        # Should NOT have Launch section (launch is empty)
        labels = [r[0] for r in rows]
        # The "[bold cyan]Launch[/bold cyan]" should not appear
        assert not any(label == "[bold cyan]Launch[/bold cyan]" for label in labels)

    def test_with_fs_rates(self):
        """Test status with filesystem rate metrics."""
        status = ServiceStatusData(
            running=True,
            fs_rate_short=1.5,
            fs_rate_long=0.5,
            fs_rate_weighted=1.0,
            pending_deletes=5,
            pending_mods=10,
        )
        rows = build_status_rows(status)

        row_dict = {r[0].strip(): r[1] for r in rows}
        assert row_dict.get("Pending deletes", "") == "5"
        assert row_dict.get("Pending mods", "") == "10"
        assert "1.50" in row_dict.get("Ops/sec (10s)", "")
        assert "0.50" in row_dict.get("Ops/sec (10m)", "")
        assert "60" in row_dict.get("Ops (last min)", "")  # 1.0 * 60

    def test_null_values(self):
        """Test status with None values shows dashes."""
        status = ServiceStatusData()
        rows = build_status_rows(status)

        row_dict = {r[0].strip(): r[1] for r in rows}
        assert row_dict.get("Uptime", "") == "-"
        assert row_dict.get("PID", "") == "-"
        assert row_dict.get("Pending deletes", "") == "-"

    def test_launch_with_arguments(self):
        """Test launch agent with arguments instead of program."""
        status = ServiceStatusData(
            running=True,
            launch=ServiceStatusLaunch(
                state="running",
                arguments="/usr/bin/python3 -m wks.api.service.daemon",
                type="LaunchAgent",
            ),
        )
        rows = build_status_rows(status)

        row_dict = {r[0].strip(): r[1] for r in rows}
        assert row_dict.get("Program", "") == "/usr/bin/python3 -m wks.api.service.daemon"
