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
        """Load state from JSON."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
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
