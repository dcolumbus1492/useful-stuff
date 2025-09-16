#!/usr/bin/env python3
"""Debug version of status line to understand timing issues."""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'hooks'))
from cost_tracker import get_tracker

# Create debug log
debug_log = Path.home() / '.claude' / 'status_line_debug.log'

def log_debug(msg):
    with open(debug_log, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        session_id = input_data.get('session_id', 'unknown')
        total_cost = input_data.get('cost', {}).get('total_cost_usd', 0.0)

        # Get tracker and state
        tracker = get_tracker()
        state = tracker._load_state(session_id)

        # Log the current state
        log_debug(f"Session: {session_id}")
        log_debug(f"Context: {state.current_context}")
        log_debug(f"In subagent: {state.in_subagent}")
        log_debug(f"Subagent type: {state.current_subagent_type}")
        log_debug(f"Total cost: {total_cost}")
        log_debug("---")

        # Just output simple status
        print(f"💰 ${total_cost:.3f} | Context: {state.current_context} | Subagent: {state.current_subagent_type or 'None'}")

    except Exception as e:
        log_debug(f"Error: {str(e)}")
        print(f"Debug status line error: {str(e)}")

if __name__ == "__main__":
    main()