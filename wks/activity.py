"""
File activity tracking with "angle" metric.

The angle represents the rate of change/attention on a file.
Higher angle = more active/important recently.
"""

import json
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class ActivityTracker:
    """Track file activity and calculate attention angles."""

    def __init__(self, state_file: Path):
        """
        Initialize activity tracker.

        Args:
            state_file: Path to JSON state file
        """
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from JSON, backing up if corrupted."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception:
                # Corrupted state; back up and start fresh
                try:
                    b = self.state_file.with_suffix('.json.backup')
                    self.state_file.rename(b)
                    print(f"Warning: Corrupted activity state backed up to {b}")
                except Exception:
                    pass
        return {}

    def _save_state(self):
        """Save state to JSON."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def record_event(self, file_path: Path, event_type: str = "modified"):
        """
        Record a file event.

        Args:
            file_path: Path to file
            event_type: Type of event
        """
        path_str = str(file_path.resolve())
        now = datetime.now().isoformat()

        if path_str not in self.state:
            self.state[path_str] = {
                "events": [],
                "angles": [],
                "created": now
            }

        self.state[path_str]["events"].append({
            "type": event_type,
            "timestamp": now
        })

        # Keep last 50 events
        if len(self.state[path_str]["events"]) > 50:
            self.state[path_str]["events"] = self.state[path_str]["events"][-50:]

        self._calculate_angle(path_str)
        self._save_state()

    def _calculate_angle(self, path_str: str):
        """
        Calculate the 'angle' for a file based on recent activity.

        The angle represents attention/change velocity.
        Higher values = more recent/frequent changes.

        Algorithm:
        - Weight recent events higher than old events
        - Exponential decay over time
        """
        events = self.state[path_str]["events"]
        if not events:
            angle = 0.0
        else:
            now = datetime.now()
            angle = 0.0

            for event in events:
                event_time = datetime.fromisoformat(event["timestamp"])
                hours_ago = (now - event_time).total_seconds() / 3600

                # Exponential decay: events lose weight over time
                # Half-life of 24 hours
                weight = math.exp(-hours_ago / 24)
                angle += weight

        self.state[path_str]["angles"].append({
            "value": angle,
            "timestamp": datetime.now().isoformat()
        })

        # Keep last 100 angle measurements
        if len(self.state[path_str]["angles"]) > 100:
            self.state[path_str]["angles"] = self.state[path_str]["angles"][-100:]

    def _compute_angle_now(self, path_str: str) -> float:
        """Compute angle for a path at the current moment without recording an event."""
        data = self.state.get(path_str) or {}
        events = data.get("events") or []
        if not events:
            return 0.0
        now = datetime.now()
        import math as _math
        angle = 0.0
        for ev in events:
            try:
                et = datetime.fromisoformat(ev.get("timestamp"))
            except Exception:
                continue
            hours_ago = (now - et).total_seconds() / 3600.0
            weight = _math.exp(-hours_ago / 24.0)
            angle += weight
        return float(angle)

    def refresh_angles_all(self):
        """Append a current angle snapshot for all tracked files to enable positive/negative slopes.

        Keeps last 100 samples; saves state.
        """
        changed = False
        now_iso = datetime.now().isoformat()
        for path_str, data in list(self.state.items()):
            try:
                angle = self._compute_angle_now(path_str)
                arr = data.setdefault("angles", [])
                arr.append({"value": angle, "timestamp": now_iso})
                if len(arr) > 100:
                    data["angles"] = arr[-100:]
                changed = True
            except Exception:
                continue
        if changed:
            self._save_state()

    def get_angle(self, file_path: Path) -> float:
        """
        Get current angle for a file.

        Args:
            file_path: Path to file

        Returns:
            Current angle value
        """
        path_str = str(file_path.resolve())
        if path_str in self.state and self.state[path_str]["angles"]:
            return self.state[path_str]["angles"][-1]["value"]
        return 0.0

    def get_angle_delta(self, file_path: Path) -> float:
        """
        Get change in angle (velocity of attention change).

        Args:
            file_path: Path to file

        Returns:
            Delta angle (current - previous)
        """
        path_str = str(file_path.resolve())
        if path_str in self.state and len(self.state[path_str]["angles"]) >= 2:
            current = self.state[path_str]["angles"][-1]["value"]
            previous = self.state[path_str]["angles"][-2]["value"]
            return current - previous
        return 0.0

    def get_top_active_files(self, limit: int = 20) -> List[Tuple[str, float, float]]:
        """
        Get most active files by angle.

        Args:
            limit: Number of files to return

        Returns:
            List of (path, angle, delta_angle) tuples, sorted by angle descending
        """
        files = []

        for path_str, data in self.state.items():
            if data["angles"]:
                angle = data["angles"][-1]["value"]
                delta = 0.0
                if len(data["angles"]) >= 2:
                    delta = angle - data["angles"][-2]["value"]

                # Only include files with significant angle
                if angle > 0.1:
                    files.append((path_str, angle, delta))

        # Sort by angle descending
        files.sort(key=lambda x: x[1], reverse=True)

        return files[:limit]

    def get_last_modified(self, file_path: Path) -> str:
        """
        Get last modification time for a file.

        Args:
            file_path: Path to file

        Returns:
            ISO timestamp of last event
        """
        path_str = str(file_path.resolve())
        if path_str in self.state and self.state[path_str]["events"]:
            return self.state[path_str]["events"][-1]["timestamp"]
        return "Never"

    def get_angle_rate_per_minute(self, file_path: Path, window_minutes: int = 60) -> float:
        """Return angle change per minute over the last window (approx).

        Uses stored angle samples; if not enough data in the window, falls back
        to using the earliest available sample vs latest. Returns 0.0 on error.
        """
        try:
            path_str = str(file_path.resolve())
            series = (self.state.get(path_str) or {}).get("angles") or []
            if len(series) < 2:
                return 0.0
            from datetime import datetime, timedelta
            now = datetime.now()
            cutoff = now - timedelta(minutes=max(1, int(window_minutes)))
            # Find first sample within window; if none, use first overall
            first_idx = None
            for i, s in enumerate(series):
                try:
                    ts = datetime.fromisoformat(s.get("timestamp"))
                except Exception:
                    continue
                if ts >= cutoff:
                    first_idx = i
                    break
            if first_idx is None:
                first_idx = 0
            first = series[first_idx]
            last = series[-1]
            try:
                t0 = datetime.fromisoformat(first.get("timestamp"))
                t1 = datetime.fromisoformat(last.get("timestamp"))
            except Exception:
                return 0.0
            minutes = max(1.0, (t1 - t0).total_seconds() / 60.0)
            return float((last.get("value", 0.0) - first.get("value", 0.0)) / minutes)
        except Exception:
            return 0.0


if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Example usage
    tracker = ActivityTracker(Path.home() / ".wks" / "activity_state.json")

    # Simulate some activity
    test_file = Path.home() / "2025-WKS" / "SPEC.md"
    for i in range(5):
        tracker.record_event(test_file, "modified")

    # Get top active files
    top_files = tracker.get_top_active_files(limit=10)

    # Display in table
    table = Table(title="Most Active Files")
    table.add_column("File", style="cyan")
    table.add_column("Angle", justify="right", style="yellow")
    table.add_column("Delta", justify="right", style="green")

    for path, angle, delta in top_files:
        table.add_row(Path(path).name, f"{angle:.2f}", f"{delta:+.2f}")

    console.print(table)
