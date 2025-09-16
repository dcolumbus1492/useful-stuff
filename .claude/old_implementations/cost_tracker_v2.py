#!/usr/bin/env python3
"""
Claude Code Advanced Cost Tracker V2
Fixed timing issues with late-arriving cost updates.
Uses time-based attribution windows to handle async updates correctly.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
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
class ContextWindow:
    """Time window for a specific execution context."""
    source: str  # 'primary', 'subagent', 'direct_mcp'
    start_time_ms: int
    end_time_ms: Optional[int] = None
    tool_name: Optional[str] = None
    subagent_type: Optional[str] = None

    def is_active_at(self, timestamp_ms: int) -> bool:
        """Check if this context was active at given timestamp."""
        if timestamp_ms < self.start_time_ms:
            return False
        if self.end_time_ms is None:
            return True
        return timestamp_ms <= self.end_time_ms

@dataclass
class CostUpdate:
    """Record of a cost update for proper attribution."""
    timestamp_ms: int
    total_cost: float
    increment: float
    attributed_to: Optional[str] = None

class CostTrackerV2:
    """
    Improved cost tracking with time-based attribution.
    Handles async cost updates that arrive after context changes.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.data_dir = Path.home() / '.claude' / 'sessions' / 'costs'
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Core state
        self.snapshots: List[CostSnapshot] = []
        self.context_windows: List[ContextWindow] = []
        self.cost_updates: List[CostUpdate] = []

        # Current state
        self.last_total_cost = 0.0
        self.in_subagent = False
        self.subagent_depth = 0
        self.active_mcp_context: Optional[ContextWindow] = None

        # Tracking
        self.costs_by_source = defaultdict(float)
        self.pending_attribution = 0.0  # Costs not yet attributed

        # Thread safety
        self._lock = Lock()

        # Grace period for late updates (5 seconds)
        self.attribution_grace_period_ms = 5000

        # Load existing data
        self._load_state()

    def _get_current_time_ms(self) -> int:
        """Get current time in milliseconds."""
        return int(time.time() * 1000)

    def _find_active_context(self, timestamp_ms: int) -> str:
        """Find which context was active at given timestamp."""
        # Look for most specific context first
        for window in reversed(self.context_windows):
            if window.is_active_at(timestamp_ms):
                # Direct MCP in primary takes precedence
                if window.source == 'direct_mcp' and not self._was_in_subagent_at(timestamp_ms):
                    return 'direct_mcp'
                # Subagent context
                elif window.source == 'subagent':
                    return 'subagent'

        # Default to primary
        return 'primary'

    def _was_in_subagent_at(self, timestamp_ms: int) -> bool:
        """Check if we were in a subagent at given time."""
        for window in self.context_windows:
            if window.source == 'subagent' and window.is_active_at(timestamp_ms):
                return True
        return False

    def _reattribute_pending_costs(self) -> None:
        """Re-attribute any pending costs based on context windows."""
        if self.pending_attribution <= 0:
            return

        # Find unattributed updates
        for update in self.cost_updates:
            if update.attributed_to is None and update.increment > 0:
                # Find context at update time
                context = self._find_active_context(update.timestamp_ms)
                update.attributed_to = context
                self.costs_by_source[context] += update.increment
                self.pending_attribution -= update.increment

    def update_total_cost(self, total_cost_usd: float) -> None:
        """
        Update total cost with smart attribution based on timing.
        """
        with self._lock:
            current_time = self._get_current_time_ms()

            if total_cost_usd <= self.last_total_cost:
                return  # No new cost

            # Calculate increment
            increment = total_cost_usd - self.last_total_cost
            self.last_total_cost = total_cost_usd

            # Record the update
            update = CostUpdate(
                timestamp_ms=current_time,
                total_cost=total_cost_usd,
                increment=increment
            )
            self.cost_updates.append(update)

            # Try to attribute based on current context
            context = self._find_active_context(current_time)
            update.attributed_to = context
            self.costs_by_source[context] += increment

            # Re-attribute any pending costs
            self._reattribute_pending_costs()

            # Record snapshot
            snapshot = CostSnapshot(
                timestamp_ms=current_time,
                total_cost_usd=total_cost_usd,
                primary_cost_usd=self.costs_by_source['primary'],
                subagent_cost_usd=self.costs_by_source['subagent'],
                direct_mcp_cost_usd=self.costs_by_source['direct_mcp']
            )
            self.snapshots.append(snapshot)

            # Persist periodically
            if len(self.snapshots) % 10 == 0:
                self._save_state()

    def on_tool_start(self, tool_name: str, tool_input: Dict) -> None:
        """Handle tool start event."""
        with self._lock:
            current_time = self._get_current_time_ms()

            if tool_name == 'Task':
                # Create subagent context window
                self.in_subagent = True
                self.subagent_depth += 1

                window = ContextWindow(
                    source='subagent',
                    start_time_ms=current_time,
                    tool_name=tool_name,
                    subagent_type=tool_input.get('subagent_type', 'unknown')
                )
                self.context_windows.append(window)

            elif tool_name.startswith('mcp__') and not self.in_subagent:
                # Direct MCP call from primary
                self.active_mcp_context = ContextWindow(
                    source='direct_mcp',
                    start_time_ms=current_time,
                    tool_name=tool_name
                )
                self.context_windows.append(self.active_mcp_context)

    def on_tool_end(self, tool_name: str) -> None:
        """Handle tool end event."""
        with self._lock:
            current_time = self._get_current_time_ms()

            if tool_name == 'Task':
                self.subagent_depth -= 1
                if self.subagent_depth == 0:
                    self.in_subagent = False

                # Close subagent window with grace period
                for window in reversed(self.context_windows):
                    if window.source == 'subagent' and window.end_time_ms is None:
                        window.end_time_ms = current_time + self.attribution_grace_period_ms
                        break

            elif tool_name.startswith('mcp__') and self.active_mcp_context:
                # Close MCP window
                self.active_mcp_context.end_time_ms = current_time
                self.active_mcp_context = None

    def on_subagent_stop(self) -> None:
        """Handle subagent stop event."""
        with self._lock:
            current_time = self._get_current_time_ms()

            # Force close all subagent contexts with grace period
            self.in_subagent = False
            self.subagent_depth = 0

            for window in self.context_windows:
                if window.source == 'subagent' and window.end_time_ms is None:
                    window.end_time_ms = current_time + self.attribution_grace_period_ms

            # Re-attribute any pending costs
            self._reattribute_pending_costs()

    def get_cost_breakdown(self) -> Dict[str, float]:
        """Get current cost breakdown by source."""
        with self._lock:
            # Re-attribute before returning
            self._reattribute_pending_costs()

            return {
                'total': self.last_total_cost,
                'primary': self.costs_by_source['primary'],
                'subagent': self.costs_by_source['subagent'],
                'direct_mcp': self.costs_by_source['direct_mcp']
            }

    def get_current_source_info(self) -> Tuple[str, Optional[str]]:
        """Get current source and optional details."""
        with self._lock:
            current_time = self._get_current_time_ms()
            source = self._find_active_context(current_time)

            # Find most recent window of this type
            for window in reversed(self.context_windows):
                if window.source == source and window.is_active_at(current_time):
                    if source == 'subagent':
                        return source, window.subagent_type
                    elif source == 'direct_mcp':
                        return source, window.tool_name
                    break

            return source, None

    def _load_state(self) -> None:
        """Load persisted state if exists."""
        state_file = self.data_dir / f"{self.session_id}_costs_v2.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.costs_by_source = defaultdict(float, data.get('costs_by_source', {}))
                    self.last_total_cost = data.get('last_total_cost', 0.0)

                    # Reconstruct windows
                    for w in data.get('context_windows', []):
                        self.context_windows.append(ContextWindow(**w))

                    # Reconstruct updates
                    for u in data.get('cost_updates', []):
                        self.cost_updates.append(CostUpdate(**u))

                    # Reconstruct snapshots
                    for s in data.get('snapshots', []):
                        self.snapshots.append(CostSnapshot(**s))
            except Exception:
                pass  # Start fresh on error

    def _save_state(self) -> None:
        """Persist current state."""
        state_file = self.data_dir / f"{self.session_id}_costs_v2.json"
        temp_file = state_file.with_suffix('.tmp')

        # Only keep recent data to avoid unbounded growth
        recent_windows = [w for w in self.context_windows
                         if w.end_time_ms is None or
                         w.end_time_ms > self._get_current_time_ms() - 3600000]  # Last hour

        data = {
            'session_id': self.session_id,
            'costs_by_source': dict(self.costs_by_source),
            'last_total_cost': self.last_total_cost,
            'context_windows': [asdict(w) for w in recent_windows],
            'cost_updates': [asdict(u) for u in self.cost_updates[-500:]],  # Last 500
            'snapshots': [asdict(s) for s in self.snapshots[-100:]]  # Last 100
        }

        try:
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.rename(state_file)
        except Exception:
            pass  # Fail silently

# Global tracker instances per session
_trackers: Dict[str, CostTrackerV2] = {}
_trackers_lock = Lock()

def get_tracker(session_id: str) -> CostTrackerV2:
    """Get or create tracker for session."""
    with _trackers_lock:
        if session_id not in _trackers:
            _trackers[session_id] = CostTrackerV2(session_id)
        return _trackers[session_id]