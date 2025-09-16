#!/usr/bin/env python3
"""
Unified Cost Hook - Updates shared state for cost attribution.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cost_tracker import get_tracker

def main():
    """Process hook events and update shared state."""
    try:
        if sys.stdin.isatty():
            sys.exit(0)

        data = json.loads(sys.stdin.read())
        session_id = data.get("session_id", "unknown")
        action = sys.argv[1] if len(sys.argv) > 1 else "unknown"

        tracker = get_tracker()

        if action == "tool_use":
            tool_name = data.get("tool_name", "")
            tool_input = data.get("tool_input", {})
            tracker.on_tool_start(session_id, tool_name, tool_input)

        elif action == "tool_result":
            tool_name = data.get("tool_name", "")
            tracker.on_tool_end(session_id, tool_name)

        elif action == "subagent_stop":
            tracker.on_subagent_stop(session_id)

    except Exception:
        pass  # Fail silently

    sys.exit(0)

if __name__ == "__main__":
    main()