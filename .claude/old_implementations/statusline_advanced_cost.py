#!/usr/bin/env python3
"""
Claude Code Advanced Status Line with Cost Breakdown by Source
Shows total cost and attribution to primary agent, subagents, and direct MCP calls.
"""

import json
import sys
import os
from pathlib import Path

# Import our cost tracker
sys.path.insert(0, str(Path(__file__).parent / 'hooks'))
from cost_tracker_v2 import get_tracker

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

    # Calculate hours, minutes, and seconds
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60

    # Format based on duration length
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

def format_cost_breakdown(breakdown):
    """Format cost breakdown with percentages."""
    total = breakdown['total']
    if total == 0:
        return ""

    parts = []

    # Only show non-zero costs
    for source in ['primary', 'subagent', 'direct_mcp']:
        cost = breakdown.get(source, 0)
        if cost > 0:
            pct = (cost / total) * 100
            emoji = get_source_emoji(source)
            parts.append(f"{emoji} {format_cost(cost)} ({pct:.0f}%)")

    return " | ".join(parts) if parts else ""

def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Extract basic information
        session_id = input_data.get('session_id', 'unknown')
        model_name = input_data.get('model', {}).get('display_name', 'Unknown')
        cost_info = input_data.get('cost', {})

        # Get cost tracker instance
        tracker = get_tracker(session_id)

        # Update tracker with latest total cost
        total_cost = cost_info.get('total_cost_usd', 0.0)
        tracker.update_total_cost(total_cost)

        # Get cost breakdown
        breakdown = tracker.get_cost_breakdown()

        # Get current context info
        current_source, source_detail = tracker.get_current_source_info()

        # Format main cost display
        cost_str = format_cost(total_cost)
        api_duration = cost_info.get('total_api_duration_ms', 0)
        duration_str = format_duration(api_duration)

        # Build status line components
        components = [f"💰 {cost_str}"]

        # Add breakdown if we have costs from multiple sources
        breakdown_str = format_cost_breakdown(breakdown)
        if breakdown_str:
            components.append(breakdown_str)

        # Add duration and model
        components.extend([
            f"⏱️  {duration_str}",
            f"[{model_name}]"
        ])

        # Show current execution context
        if current_source != 'primary':
            emoji = get_source_emoji(current_source)
            if source_detail:
                components.append(f"{emoji} {source_detail}")
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

        # Output the status line
        print(" | ".join(components))

    except Exception as e:
        # Fallback status line on error
        print(f"💰 Advanced cost tracker | Error: {str(e)}")

if __name__ == "__main__":
    main()