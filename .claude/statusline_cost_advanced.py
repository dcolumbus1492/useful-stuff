#!/usr/bin/env python3
"""
Unified Cost Status Line - Reads from shared state maintained by hooks.
"""

import json
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'hooks'))
from cost_tracker import get_tracker

def format_cost(cost_usd):
    """Format cost in USD with appropriate precision."""
    if cost_usd < 0.01:
        return f"${cost_usd:.4f}"
    elif cost_usd < 1.0:
        return f"${cost_usd:.3f}"
    else:
        return f"${cost_usd:.2f}"

def format_duration(duration_ms):
    """Format duration from milliseconds to human-readable format."""
    if duration_ms is None:
        return "0s"

    total_seconds = duration_ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h {minutes}m {seconds:.1f}s"
    elif minutes > 0:
        return f"{minutes}m {seconds:.1f}s"
    else:
        return f"{seconds:.1f}s"

def get_source_emoji(source):
    """Get emoji for each cost source."""
    return {
        'primary': '🤖',
        'subagent': '🚀',
        'direct_mcp': '🔌'
    }.get(source, '❓')

def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Extract information
        session_id = input_data.get('session_id', 'unknown')
        model_name = input_data.get('model', {}).get('display_name', 'Unknown')
        cost_info = input_data.get('cost', {})
        total_cost = cost_info.get('total_cost_usd', 0.0)

        # Get tracker and update with latest cost
        tracker = get_tracker()
        breakdown = tracker.update_cost_and_get_breakdown(session_id, total_cost)

        # Always load current state to show real-time context
        # This ensures we show context changes even without cost updates
        state = tracker._load_state(session_id)
        breakdown['current_context'] = state.current_context
        breakdown['context_detail'] = state.current_subagent_type or state.current_mcp_tool

        # Build status line
        cost_str = format_cost(total_cost)
        components = [f"💰 {cost_str}"]

        # Add breakdown if we have costs from multiple sources
        has_multiple_sources = sum(1 for k, v in breakdown.items()
                                  if k in ['primary', 'subagent', 'direct_mcp'] and v > 0) > 1

        if has_multiple_sources:
            parts = []
            for source in ['primary', 'subagent', 'direct_mcp']:
                source_cost = breakdown.get(source, 0)
                if source_cost > 0 and total_cost > 0:
                    pct = (source_cost / total_cost) * 100
                    emoji = get_source_emoji(source)
                    parts.append(f"{emoji} {format_cost(source_cost)} ({pct:.0f}%)")
            if parts:
                components.append(" | ".join(parts))

        # Add duration and model
        api_duration = cost_info.get('total_api_duration_ms', 0)
        duration_str = format_duration(api_duration)
        components.extend([
            f"⏱️  {duration_str}",
            f"[{model_name}]"
        ])

        # Show current execution context
        current_context = breakdown.get('current_context', 'primary')
        context_detail = breakdown.get('context_detail')

        if current_context != 'primary':
            emoji = get_source_emoji(current_context)
            if context_detail:
                components.append(f"{emoji} {context_detail}")
            else:
                components.append(f"{emoji} Active")

        # Add code changes if any
        lines_added = cost_info.get('total_lines_added', 0)
        lines_removed = cost_info.get('total_lines_removed', 0)
        if lines_added > 0 or lines_removed > 0:
            components.append(f"📝 +{lines_added}/-{lines_removed}")

        # Get current directory name
        current_dir = input_data.get('workspace', {}).get('current_dir', '')
        if current_dir:
            dir_name = os.path.basename(current_dir)
            components.append(f"📁 {dir_name}")

        # Add activity indicator based on time since last update
        current_time_ms = int(time.time() * 1000)
        if hasattr(state, 'last_updated_ms'):
            time_since_update = (current_time_ms - state.last_updated_ms) / 1000
            if time_since_update < 2:
                components.append("●")  # Active
            elif time_since_update < 10:
                components.append("◐")  # Recent activity
            else:
                components.append("◯")  # Idle

        # Output the status line
        print(" | ".join(components))

    except Exception as e:
        # Fallback status line on error
        print(f"💰 Cost tracker | Error: {str(e)}")

if __name__ == "__main__":
    main()