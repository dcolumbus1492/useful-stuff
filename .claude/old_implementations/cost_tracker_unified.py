#!/usr/bin/env python3
"""
Unified Cost Tracker - Google-level elegant solution
Tracks execution contexts through hooks and provides cost attribution for status line.
"""

import json
import time
import fcntl
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from threading import Lock

@dataclass
class SessionState:
    """Persistent session state shared between hooks and status line."""
    session_id: str
    current_source: str = 'primary'
    in_subagent: bool = False
    subagent_depth: int = 0
    current_subagent_type: Optional[str] = None
    current_mcp_tool: Optional[str] = None

    # Cost tracking
    last_total_cost: float = 0.0
    costs_by_source: Dict[str, float] = None

    # Timing for attribution
    last_context_change_ms: int = 0

    def __post_init__(self):
        if self.costs_by_source is None:
            self.costs_by_source = {'primary': 0.0, 'subagent': 0.0, 'direct_mcp': 0.0}

class UnifiedCostTracker:
    """
    Singleton tracker that maintains state across all hook invocations.
    Uses file-based locking for true persistence between processes.
    """

    def __init__(self):
        self.state_dir = Path.home() / '.claude' / 'sessions' / 'cost_state'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._local_cache: Dict[str, SessionState] = {}
        self._lock = Lock()

    def _get_state_file(self, session_id: str) -> Path:
        """Get state file path for session."""
        return self.state_dir / f"{session_id}.state.json"

    def _load_state(self, session_id: str) -> SessionState:
        """Load state from file with locking."""
        state_file = self._get_state_file(session_id)

        try:
            with open(state_file, 'r') as f:
                # Shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                # Reconstruct state
                state = SessionState(
                    session_id=data['session_id'],
                    current_source=data.get('current_source', 'primary'),
                    in_subagent=data.get('in_subagent', False),
                    subagent_depth=data.get('subagent_depth', 0),
                    current_subagent_type=data.get('current_subagent_type'),
                    current_mcp_tool=data.get('current_mcp_tool'),
                    last_total_cost=data.get('last_total_cost', 0.0),
                    costs_by_source=data.get('costs_by_source', {}),
                    last_context_change_ms=data.get('last_context_change_ms', 0)
                )
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            # Create new state
            return SessionState(session_id=session_id)

    def _save_state(self, state: SessionState) -> None:
        """Save state to file with exclusive locking."""
        state_file = self._get_state_file(state.session_id)
        temp_file = state_file.with_suffix('.tmp')

        data = {
            'session_id': state.session_id,
            'current_source': state.current_source,
            'in_subagent': state.in_subagent,
            'subagent_depth': state.subagent_depth,
            'current_subagent_type': state.current_subagent_type,
            'current_mcp_tool': state.current_mcp_tool,
            'last_total_cost': state.last_total_cost,
            'costs_by_source': state.costs_by_source,
            'last_context_change_ms': state.last_context_change_ms,
            'last_updated_ms': int(time.time() * 1000)
        }

        try:
            with open(temp_file, 'w') as f:
                # Exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Atomic rename
            temp_file.rename(state_file)
        except Exception:
            pass  # Fail silently

    def on_tool_start(self, session_id: str, tool_name: str, tool_input: Dict) -> None:
        """Handle tool start event from hook."""
        with self._lock:
            state = self._load_state(session_id)
            state.last_context_change_ms = int(time.time() * 1000)

            if tool_name == 'Task':
                # Entering subagent
                state.in_subagent = True
                state.subagent_depth += 1
                state.current_subagent_type = tool_input.get('subagent_type', 'unknown')
                state.current_source = 'subagent'

            elif tool_name.startswith('mcp__') and not state.in_subagent:
                # Direct MCP call from primary
                state.current_mcp_tool = tool_name
                state.current_source = 'direct_mcp'

            self._save_state(state)

    def on_tool_end(self, session_id: str, tool_name: str) -> None:
        """Handle tool end event from hook."""
        with self._lock:
            state = self._load_state(session_id)
            state.last_context_change_ms = int(time.time() * 1000)

            if tool_name == 'Task':
                state.subagent_depth -= 1
                if state.subagent_depth == 0:
                    state.in_subagent = False
                    state.current_subagent_type = None
                    state.current_source = 'primary'

            elif tool_name.startswith('mcp__') and tool_name == state.current_mcp_tool:
                # Exiting direct MCP
                state.current_mcp_tool = None
                state.current_source = 'primary'

            self._save_state(state)

    def on_subagent_stop(self, session_id: str) -> None:
        """Handle subagent stop event."""
        with self._lock:
            state = self._load_state(session_id)
            state.last_context_change_ms = int(time.time() * 1000)

            # Force exit subagent
            state.in_subagent = False
            state.subagent_depth = 0
            state.current_subagent_type = None
            state.current_source = 'primary'

            self._save_state(state)

    def update_cost_from_status_line(self, session_id: str, total_cost: float) -> Dict[str, float]:
        """
        Called from status line to update costs and get breakdown.
        This is where the magic happens - we attribute based on current context.
        """
        with self._lock:
            state = self._load_state(session_id)

            if total_cost > state.last_total_cost:
                # Calculate increment
                increment = total_cost - state.last_total_cost
                state.last_total_cost = total_cost

                # Attribute to current source
                state.costs_by_source[state.current_source] += increment

                # Save updated state
                self._save_state(state)

            # Return current breakdown
            return {
                'total': state.last_total_cost,
                'primary': state.costs_by_source['primary'],
                'subagent': state.costs_by_source['subagent'],
                'direct_mcp': state.costs_by_source['direct_mcp'],
                'current_source': state.current_source,
                'current_detail': state.current_subagent_type or state.current_mcp_tool
            }

# Global singleton instance
_tracker = UnifiedCostTracker()

def get_tracker() -> UnifiedCostTracker:
    """Get the global tracker instance."""
    return _tracker