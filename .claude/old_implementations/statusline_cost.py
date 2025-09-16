#!/usr/bin/env python3
"""
Claude Code custom status line that displays session cost in real-time.
This script receives JSON input from Claude Code and outputs a formatted status line.
"""

import json
import sys
import os

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

def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Extract relevant information
        model_name = input_data.get('model', {}).get('display_name', 'Unknown')
        cost_info = input_data.get('cost', {})

        # Extract cost metrics
        total_cost = cost_info.get('total_cost_usd', 0.0)
        api_duration = cost_info.get('total_api_duration_ms', 0)
        lines_added = cost_info.get('total_lines_added', 0)
        lines_removed = cost_info.get('total_lines_removed', 0)

        # Format the status line
        cost_str = format_cost(total_cost)
        duration_str = format_duration(api_duration)

        # Build status line components
        components = [
            f"💰 {cost_str}",
            f"⏱️  {duration_str}",
            f"[{model_name}]",
        ]

        # Add code changes if any
        if lines_added > 0 or lines_removed > 0:
            components.append(f"📝 +{lines_added}/-{lines_removed}")

        # Get current directory name
        current_dir = input_data.get('workspace', {}).get('current_dir', '')
        if current_dir:
            dir_name = os.path.basename(current_dir)
            components.append(f"📁 {dir_name}")

        # Check for git branch
        try:
            git_branch = os.popen('git branch --show-current 2>/dev/null').read().strip()
            if git_branch:
                components.append(f"🌿 {git_branch}")
        except:
            pass

        # Output the status line
        print(" | ".join(components))

    except Exception as e:
        # Fallback status line on error
        print(f"💰 Cost tracker | Error: {str(e)}")

if __name__ == "__main__":
    main()