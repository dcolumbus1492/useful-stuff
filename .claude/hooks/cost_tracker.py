#!/usr/bin/env python3
"""
Final Cost Tracker - Properly handles incremental cost attribution.
The key insight: We need to track cost DELTAS between status updates.
"""

import json
import time
import fcntl
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from collections import deque

@dataclass
class CostCheckpoint:
    """A point-in-time cost snapshot with context."""
    timestamp_ms: int
    total_cost: float
    context: str  # 'primary', 'subagent', 'direct_mcp'
    subagent_type: Optional[str] = None
    mcp_tool: Optional[str] = None

@dataclass
class SessionState:
    """Persistent session state with cost history."""
    session_id: str

    # Current execution context
    current_context: str = 'primary'
    in_subagent: bool = False
    subagent_depth: int = 0
    current_subagent_type: Optional[str] = None
    current_mcp_tool: Optional[str] = None

    # Cost tracking with history
    last_total_cost: float = 0.0
    cost_checkpoints: List[dict] = None  # List of checkpoint dicts for JSON serialization

    # Accumulated costs by source
    primary_cost: float = 0.0
    subagent_cost: float = 0.0
    direct_mcp_cost: float = 0.0

    def __post_init__(self):
        if self.cost_checkpoints is None:
            self.cost_checkpoints = []

    def add_checkpoint(self, total_cost: float) -> None:
        """Add a cost checkpoint with current context."""
        checkpoint = CostCheckpoint(
            timestamp_ms=int(time.time() * 1000),
            total_cost=total_cost,
            context=self.current_context,
            subagent_type=self.current_subagent_type if self.current_context == 'subagent' else None,
            mcp_tool=self.current_mcp_tool if self.current_context == 'direct_mcp' else None
        )
        self.cost_checkpoints.append(asdict(checkpoint))

        # Keep only last 1000 checkpoints to prevent unbounded growth
        if len(self.cost_checkpoints) > 1000:
            self.cost_checkpoints = self.cost_checkpoints[-1000:]

    def calculate_costs(self) -> Dict[str, float]:
        """
        Recalculate all costs from checkpoint history.
        This is the key - we attribute each cost delta to the context at that time.
        """
        primary = 0.0
        subagent = 0.0
        direct_mcp = 0.0

        # Convert checkpoint dicts back to objects for processing
        checkpoints = [CostCheckpoint(**cp) for cp in self.cost_checkpoints]

        # Process each checkpoint delta
        for i in range(1, len(checkpoints)):
            prev = checkpoints[i-1]
            curr = checkpoints[i]

            # Calculate delta
            delta = curr.total_cost - prev.total_cost
            if delta <= 0:
                continue

            # Attribute to the context at the PREVIOUS checkpoint
            # (costs are for work done in that context)
            if prev.context == 'primary':
                primary += delta
            elif prev.context == 'subagent':
                subagent += delta
            elif prev.context == 'direct_mcp':
                direct_mcp += delta

        # Handle the very first checkpoint
        if checkpoints and checkpoints[0].total_cost > 0:
            if checkpoints[0].context == 'primary':
                primary += checkpoints[0].total_cost
            elif checkpoints[0].context == 'subagent':
                subagent += checkpoints[0].total_cost
            elif checkpoints[0].context == 'direct_mcp':
                direct_mcp += checkpoints[0].total_cost

        # Update cached values
        self.primary_cost = primary
        self.subagent_cost = subagent
        self.direct_mcp_cost = direct_mcp

        return {
            'primary': primary,
            'subagent': subagent,
            'direct_mcp': direct_mcp
        }

class FinalCostTracker:
    """
    The final, working cost tracker.
    Key improvements:
    1. Tracks cost checkpoints with context
    2. Recalculates attribution from full history
    3. Handles timing issues by looking at deltas
    """

    def __init__(self):
        self.state_dir = Path.home() / '.claude' / 'sessions' / 'cost_state_final'
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, session_id: str) -> Path:
        return self.state_dir / f"{session_id}.state.json"

    def _load_state(self, session_id: str) -> SessionState:
        """Load state with file locking."""
        state_file = self._get_state_file(session_id)

        try:
            with open(state_file, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

                # Create state from dict
                state = SessionState(
                    session_id=data['session_id'],
                    current_context=data.get('current_context', 'primary'),
                    in_subagent=data.get('in_subagent', False),
                    subagent_depth=data.get('subagent_depth', 0),
                    current_subagent_type=data.get('current_subagent_type'),
                    current_mcp_tool=data.get('current_mcp_tool'),
                    last_total_cost=data.get('last_total_cost', 0.0),
                    cost_checkpoints=data.get('cost_checkpoints', []),
                    primary_cost=data.get('primary_cost', 0.0),
                    subagent_cost=data.get('subagent_cost', 0.0),
                    direct_mcp_cost=data.get('direct_mcp_cost', 0.0)
                )
                return state
        except (FileNotFoundError, json.JSONDecodeError):
            return SessionState(session_id=session_id)

    def _save_state(self, state: SessionState) -> None:
        """Save state with exclusive locking."""
        state_file = self._get_state_file(state.session_id)
        temp_file = state_file.with_suffix('.tmp')

        data = {
            'session_id': state.session_id,
            'current_context': state.current_context,
            'in_subagent': state.in_subagent,
            'subagent_depth': state.subagent_depth,
            'current_subagent_type': state.current_subagent_type,
            'current_mcp_tool': state.current_mcp_tool,
            'last_total_cost': state.last_total_cost,
            'cost_checkpoints': state.cost_checkpoints,
            'primary_cost': state.primary_cost,
            'subagent_cost': state.subagent_cost,
            'direct_mcp_cost': state.direct_mcp_cost,
            'last_updated_ms': int(time.time() * 1000)
        }

        try:
            with open(temp_file, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            temp_file.rename(state_file)
        except Exception:
            pass

    def on_tool_start(self, session_id: str, tool_name: str, tool_input: Dict) -> None:
        """Update context when tool starts."""
        state = self._load_state(session_id)

        if tool_name == 'Task':
            # Entering subagent
            state.in_subagent = True
            state.subagent_depth += 1
            state.current_subagent_type = tool_input.get('subagent_type', 'unknown')
            state.current_context = 'subagent'

        elif tool_name.startswith('mcp__') and not state.in_subagent:
            # Direct MCP from primary
            state.current_mcp_tool = tool_name
            state.current_context = 'direct_mcp'

        self._save_state(state)

    def on_tool_end(self, session_id: str, tool_name: str) -> None:
        """Update context when tool ends."""
        state = self._load_state(session_id)

        if tool_name == 'Task':
            state.subagent_depth -= 1
            if state.subagent_depth == 0:
                state.in_subagent = False
                state.current_subagent_type = None
                state.current_context = 'primary'

        elif tool_name.startswith('mcp__') and tool_name == state.current_mcp_tool:
            state.current_mcp_tool = None
            state.current_context = 'primary'

        self._save_state(state)

    def on_subagent_stop(self, session_id: str) -> None:
        """Force exit subagent context."""
        state = self._load_state(session_id)

        state.in_subagent = False
        state.subagent_depth = 0
        state.current_subagent_type = None
        state.current_context = 'primary'

        self._save_state(state)

    def update_cost_and_get_breakdown(self, session_id: str, total_cost: float) -> Dict:
        """
        Update cost from status line and return breakdown.
        This is called frequently (every 300ms when status updates).
        """
        state = self._load_state(session_id)

        # Only add checkpoint if cost changed
        if total_cost != state.last_total_cost:
            state.add_checkpoint(total_cost)
            state.last_total_cost = total_cost

            # Recalculate all costs from checkpoint history
            state.calculate_costs()

            self._save_state(state)

        # Return current breakdown
        return {
            'total': total_cost,
            'primary': state.primary_cost,
            'subagent': state.subagent_cost,
            'direct_mcp': state.direct_mcp_cost,
            'current_context': state.current_context,
            'context_detail': state.current_subagent_type or state.current_mcp_tool
        }

# Global instance
_tracker = FinalCostTracker()

def get_tracker() -> FinalCostTracker:
    return _tracker