# Advanced Cost Tracking for Claude Code

## Overview

This implementation provides sophisticated cost tracking that distinguishes between:
- **Primary agent costs**: Direct operations from the main Claude instance
- **Subagent costs**: All costs incurred within Task tool calls (including their MCP calls)
- **Direct MCP costs**: MCP calls made directly by the primary agent

## Architecture

### 1. Cost Tracker (`hooks/cost_tracker.py`)
- Maintains persistent state across hook invocations
- Tracks cost checkpoints with execution context
- Calculates cost attribution by analyzing deltas between checkpoints
- Uses file-based storage with locking for thread safety

### 2. Cost Hook (`hooks/cost_hook.py`)
- Lightweight hook that updates execution context
- Triggered by PreToolUse, PostToolUse, and SubagentStop events
- Updates shared state when tools start/end

### 3. Status Line (`statusline_cost_advanced.py`)
- Displays real-time cost breakdown with percentages
- Shows current execution context (🤖 Primary, 🚀 Subagent, 🔌 MCP)
- Updates every 300ms with latest cost and context information

## How It Works

1. **Context Tracking**: Hooks track when entering/exiting subagents or MCP calls
2. **Cost Checkpoints**: Every cost update creates a checkpoint with current context
3. **Delta Attribution**: Cost increases are attributed to the context active at that time
4. **Real-time Display**: Status line shows both cost breakdown and current context

## Example Output

```
💰 $2.79 | 🤖 $1.50 (54%) | 🚀 $0.89 (32%) | 🔌 $0.40 (14%) | ⏱️ 3m 24.8s | [Opus 4] | 📁 project
```

When inside a subagent:
```
💰 $1.50 | 🤖 $0.80 (53%) | 🚀 $0.70 (47%) | ⏱️ 2m 10.0s | [Opus 4] | 🚀 web-content | 📁 project
```

## Files

- `/hooks/cost_tracker.py` - Core tracking logic
- `/hooks/cost_hook.py` - Hook integration
- `/statusline_cost_advanced.py` - Status line display
- `/sessions/cost_state_final/` - Persistent state storage

## Configuration

The system is configured in `.claude/settings.json` with hooks for:
- PreToolUse
- PostToolUse
- SubagentStop

And status line configuration pointing to the advanced cost script.