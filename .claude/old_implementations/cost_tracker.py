#!/usr/bin/env python3
"""
Claude Code Advanced Cost Tracker
Tracks costs by source: primary agent, subagents (Task calls), and direct MCP calls.
Understands that subagents can make their own MCP calls.
Google-level quality with elegant, non-over-engineered design.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
from threading import Lock

@dataclass
class CostSnapshot:
    """Immutable snapshot of costs at a point in time."""
    timestamp_ms: int
    total_cost_usd: float
    primary_cost_usd: float = 0.0
    subagent_cost_usd: float = 0.0  # Includes MCP calls made by subagents
    direct_mcp_cost_usd: float = 0.0  # Only MCP calls from primary agent

@dataclass
class ExecutionContext:
    """Current execution context with proper nesting understanding."""
    source: str  # 'primary', 'subagent', 'direct_mcp'
    in_subagent: bool = False  # True when inside a Task call
    tool_name: Optional[str] = None
    subagent_type: Optional[str] = None
    start_cost: Optional[float] = None

class CostTracker:
    """
    Elegant cost tracking by source with proper nesting understanding.
    Uses a simple state machine and incremental cost calculation.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.data_dir = Path.home() / '.claude' / 'sessions' / 'costs'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Core state
        self.snapshots: List[CostSnapshot] = []
        self.context_stack: List[ExecutionContext] = []
        self.last_total_cost = 0.0

        # Track if we're inside a subagent
        self.in_subagent = False
        self.subagent_depth = 0  # Handle nested subagents

        # Efficient tracking
        self.costs_by_source = defaultdict(float)
        self.tool_counts = defaultdict(int)

        # Thread safety for concurrent access
        self._lock = Lock()

        # Load existing data
        self._load_state()

    def get_current_source(self) -> str:
        """Determine current cost source based on context."""
        if self.in_subagent:
            return 'subagent'
        # Check if we're in a direct MCP call from primary
        if self.context_stack:
            last_context = self.context_stack[-1]
            if last_context.source == 'direct_mcp':
                return 'direct_mcp'
        return 'primary'

    def update_total_cost(self, total_cost_usd: float) -> None:
        """
        Update total cost from status line data.
        Distributes incremental cost to current source.
        """
        with self._lock:
            if total_cost_usd <= self.last_total_cost:
                return  # No new cost

            # Calculate increment
            increment = total_cost_usd - self.last_total_cost
            self.last_total_cost = total_cost_usd

            # Attribute to current source
            source = self.get_current_source()
            self.costs_by_source[source] += increment

            # Record snapshot
            snapshot = CostSnapshot(
                timestamp_ms=int(time.time() * 1000),
                total_cost_usd=total_cost_usd,
                primary_cost_usd=self.costs_by_source['primary'],
                subagent_cost_usd=self.costs_by_source['subagent'],
                direct_mcp_cost_usd=self.costs_by_source['direct_mcp']
            )
            self.snapshots.append(snapshot)

            # Persist periodically (every 10 snapshots)
            if len(self.snapshots) % 10 == 0:
                self._save_state()

    def on_tool_start(self, tool_name: str, tool_input: Dict) -> None:
        """Handle tool start event."""
        with self._lock:
            self.tool_counts[tool_name] += 1

            if tool_name == 'Task':
                # Entering subagent
                self.in_subagent = True
                self.subagent_depth += 1
                subagent_type = tool_input.get('subagent_type', 'unknown')
                context = ExecutionContext(
                    source='subagent',
                    in_subagent=True,
                    tool_name=tool_name,
                    subagent_type=subagent_type,
                    start_cost=self.last_total_cost
                )
                self.context_stack.append(context)

            elif tool_name.startswith('mcp__') and not self.in_subagent:
                # Direct MCP call from primary agent only
                context = ExecutionContext(
                    source='direct_mcp',
                    in_subagent=False,
                    tool_name=tool_name,
                    start_cost=self.last_total_cost
                )
                self.context_stack.append(context)

    def on_tool_end(self, tool_name: str) -> None:
        """Handle tool end event."""
        with self._lock:
            if tool_name == 'Task':
                # Exiting subagent
                self.subagent_depth -= 1
                if self.subagent_depth == 0:
                    self.in_subagent = False
                # Pop the Task context
                if self.context_stack and self.context_stack[-1].source == 'subagent':
                    self.context_stack.pop()

            elif tool_name.startswith('mcp__') and not self.in_subagent:
                # Exiting direct MCP call
                if self.context_stack and self.context_stack[-1].source == 'direct_mcp':
                    self.context_stack.pop()

    def on_subagent_stop(self) -> None:
        """Handle subagent stop event."""
        with self._lock:
            # Force exit subagent context (handles edge cases)
            self.in_subagent = False
            self.subagent_depth = 0
            # Clean up any hanging subagent contexts
            self.context_stack = [c for c in self.context_stack if c.source != 'subagent']

    def get_cost_breakdown(self) -> Dict[str, float]:
        """Get current cost breakdown by source."""
        with self._lock:
            return {
                'total': self.last_total_cost,
                'primary': self.costs_by_source['primary'],
                'subagent': self.costs_by_source['subagent'],
                'direct_mcp': self.costs_by_source['direct_mcp']
            }

    def get_current_source_info(self) -> Tuple[str, Optional[str]]:
        """Get current source and optional details."""
        with self._lock:
            source = self.get_current_source()

            if source == 'subagent' and self.context_stack:
                # Find the most recent subagent context
                for ctx in reversed(self.context_stack):
                    if ctx.source == 'subagent':
                        return source, ctx.subagent_type

            elif source == 'direct_mcp' and self.context_stack:
                return source, self.context_stack[-1].tool_name

            return source, None

    def _load_state(self) -> None:
        """Load persisted state if exists."""
        state_file = self.data_dir / f"{self.session_id}_costs.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.costs_by_source = defaultdict(float, data.get('costs_by_source', {}))
                    self.last_total_cost = data.get('last_total_cost', 0.0)
                    self.tool_counts = defaultdict(int, data.get('tool_counts', {}))
                    # Reconstruct snapshots
                    for s in data.get('snapshots', []):
                        self.snapshots.append(CostSnapshot(**s))
            except Exception:
                pass  # Start fresh on error

    def _save_state(self) -> None:
        """Persist current state."""
        state_file = self.data_dir / f"{self.session_id}_costs.json"
        temp_file = state_file.with_suffix('.tmp')

        data = {
            'session_id': self.session_id,
            'costs_by_source': dict(self.costs_by_source),
            'last_total_cost': self.last_total_cost,
            'tool_counts': dict(self.tool_counts),
            'snapshots': [asdict(s) for s in self.snapshots[-100:]]  # Keep last 100
        }

        try:
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.rename(state_file)
        except Exception:
            pass  # Fail silently

# Global tracker instances per session
_trackers: Dict[str, CostTracker] = {}
_trackers_lock = Lock()

def get_tracker(session_id: str) -> CostTracker:
    """Get or create tracker for session."""
    with _trackers_lock:
        if session_id not in _trackers:
            _trackers[session_id] = CostTracker(session_id)
        return _trackers[session_id]