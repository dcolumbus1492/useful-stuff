#!/usr/bin/env python3
"""
Cost Attribution Hook - Integrates with existing session logger
Minimal, elegant integration that tracks cost attribution without over-engineering.
"""

import json
import sys
from pathlib import Path

# Import cost tracker
sys.path.insert(0, str(Path(__file__).parent))
from cost_tracker_v2 import get_tracker

def main():
    """Process hook events for cost attribution."""
    try:
        # Read JSON input
        if sys.stdin.isatty():
            sys.exit(0)

        data = json.loads(sys.stdin.read())
        session_id = data.get("session_id", "unknown")

        # Get action from command line
        action = sys.argv[1] if len(sys.argv) > 1 else "unknown"

        # Get tracker instance
        tracker = get_tracker(session_id)

        # Handle different hook events
        if action == "tool_use":
            tool_name = data.get("tool_name", "")
            tool_input = data.get("tool_input", {})
            tracker.on_tool_start(tool_name, tool_input)

        elif action == "tool_result":
            tool_name = data.get("tool_name", "")
            tracker.on_tool_end(tool_name)

        elif action == "subagent_stop":
            tracker.on_subagent_stop()

        elif action == "status_update":
            # This would be called from a Status hook if we add one
            cost_info = data.get("cost", {})
            total_cost = cost_info.get("total_cost_usd", 0.0)
            if total_cost > 0:
                tracker.update_total_cost(total_cost)

    except Exception:
        pass  # Fail silently

    sys.exit(0)

if __name__ == "__main__":
    main()