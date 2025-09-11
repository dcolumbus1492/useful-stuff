# Claude Code Session Logger - Simple Implementation

## Overview

A lightweight session logger that captures all Claude Code events into a compressed format. Each event is one line in a JSONL file, reducing session context to <1% of original tokens while maintaining comprehension.

## Event Format

Each line in the session log:
```json
{"ts":"2025-01-11T21:45:23Z","type":"Read","target":"/path/to/file.py","status":"ok"}
{"ts":"2025-01-11T21:45:24Z","type":"USER","target":"implement the search function","status":"ok"}
{"ts":"2025-01-11T21:45:25Z","type":"Task","target":"firecrawl-mcp: scrape documentation","status":"ok"}
{"ts":"2025-01-11T21:45:30Z","type":"mcp__firecrawl__scrape","target":"https://docs.example.com","status":"ok"}
```

## Implementation

### 1. Hook Configuration (.claude/settings.json)

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py session_start"
      }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py user_prompt"
      }]
    }],
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py tool_use"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py tool_result"
      }]
    }],
    "SubagentStop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py subagent_stop"
      }]
    }],
    "SessionEnd": [{
      "hooks": [{
        "type": "command",
        "command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/session_logger.py session_end"
      }]
    }]
  }
}
```

### 2. Session Logger Script (.claude/hooks/session_logger.py)

```python
#!/usr/bin/env python3
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Session log location
SESSION_DIR = Path.home() / ".claude" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

def extract_target(tool_name, tool_input):
    """Extract the most relevant parameter from tool input"""
    if not tool_input:
        return ""
    
    # Standard tools
    if tool_name in ["Read", "Write", "Edit", "MultiEdit"]:
        return tool_input.get("file_path", "")
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Truncate long commands
        return cmd if len(cmd) <= 100 else cmd[:97] + "..."
    elif tool_name in ["Grep", "Glob"]:
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", ".")
        return f"{pattern} in {path}"
    elif tool_name == "Task":
        return f"{tool_input.get('subagent_type', 'agent')}: {tool_input.get('description', '')}"
    elif tool_name == "WebFetch":
        return tool_input.get("url", "")
    elif tool_name.startswith("mcp__"):
        # MCP tools - extract first string parameter
        for key, value in tool_input.items():
            if isinstance(value, str) and value:
                return value[:100]
    
    # Default: first string value
    for value in tool_input.values():
        if isinstance(value, str) and value:
            return value[:100]
    return "unknown"

def log_event(session_id, event_type, target="", status="ok"):
    """Log a single event to the session file"""
    event = {
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "type": event_type,
        "target": target,
        "status": status
    }
    
    log_file = SESSION_DIR / f"{session_id}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def main():
    # Read hook data from stdin
    data = json.load(sys.stdin)
    action = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    
    session_id = data.get("session_id", "unknown")
    
    if action == "session_start":
        source = data.get("source", "unknown")
        log_event(session_id, "SESSION_START", source)
        
    elif action == "user_prompt":
        prompt = data.get("prompt", "")
        # First 100 chars of prompt
        prompt_summary = prompt[:100] + "..." if len(prompt) > 100 else prompt
        log_event(session_id, "USER", prompt_summary)
        
    elif action == "tool_use":
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})
        target = extract_target(tool_name, tool_input)
        log_event(session_id, tool_name, target)
        
    elif action == "tool_result":
        # Optionally log failures
        tool_name = data.get("tool_name", "unknown")
        tool_response = data.get("tool_response", {})
        if isinstance(tool_response, dict) and tool_response.get("error"):
            target = extract_target(tool_name, data.get("tool_input", {}))
            log_event(session_id, tool_name, target, "error")
        
    elif action == "subagent_stop":
        log_event(session_id, "SUBAGENT_COMPLETE")
        
    elif action == "session_end":
        reason = data.get("reason", "unknown")
        log_event(session_id, "SESSION_END", reason)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Log errors but don't block
        print(f"Session logger error: {e}", file=sys.stderr)
        sys.exit(0)
```

### 3. Session Reader (for agents)

```python
#!/usr/bin/env python3
import json
from pathlib import Path

def read_session(session_id):
    """Read session and format for LLM consumption"""
    log_file = Path.home() / ".claude" / "sessions" / f"{session_id}.jsonl"
    
    if not log_file.exists():
        return "No session log found"
    
    # Format as ultra-compressed text
    lines = []
    with open(log_file) as f:
        for line in f:
            event = json.loads(line)
            # Even more compressed format for LLM
            if event["type"] == "USER":
                lines.append(f"USER: {event['target']}")
            elif event["type"] in ["SESSION_START", "SESSION_END", "SUBAGENT_COMPLETE"]:
                lines.append(f"[{event['type']}]")
            else:
                # Tool usage - ultra compressed
                lines.append(f"{event['type']}({event['target']})")
    
    return "\n".join(lines)

# Example output:
# [SESSION_START]
# USER: implement bash validator improvements
# Read(/Users/dave/.claude/hooks/bash_validator.py)
# Task(claude-code-docs: Research Hooks feature)
# mcp__firecrawl__scrape(https://docs.claude.ai)
# Write(~/.claude/hooks/bash_validator_improved.py)
# Bash(mv ~/.claude/hooks/bash_validator.py ~/.claude/hooks/bash_validator_old.py)
# [SESSION_END]
```

## Example Session Log

Raw JSONL file (~/.claude/sessions/abc123.jsonl):
```json
{"ts":"2025-01-11T21:45:23Z","type":"SESSION_START","target":"startup","status":"ok"}
{"ts":"2025-01-11T21:45:25Z","type":"USER","target":"create a function to validate email addresses","status":"ok"}
{"ts":"2025-01-11T21:45:26Z","type":"Read","target":"/src/validators.py","status":"ok"}
{"ts":"2025-01-11T21:45:28Z","type":"Write","target":"/src/email_validator.py","status":"ok"}
{"ts":"2025-01-11T21:45:30Z","type":"Bash","target":"python -m pytest tests/test_email.py","status":"ok"}
{"ts":"2025-01-11T21:45:32Z","type":"Task","target":"context7-docs: fetch regex documentation","status":"ok"}
{"ts":"2025-01-11T21:45:35Z","type":"mcp__context7__get-library-docs","target":"python/re","status":"ok"}
{"ts":"2025-01-11T21:45:40Z","type":"Edit","target":"/src/email_validator.py","status":"ok"}
{"ts":"2025-01-11T21:45:42Z","type":"SESSION_END","target":"user_exit","status":"ok"}
```

Formatted for LLM (69 tokens vs ~5000 original):
```
[SESSION_START]
USER: create a function to validate email addresses
Read(/src/validators.py)
Write(/src/email_validator.py)
Bash(python -m pytest tests/test_email.py)
Task(context7-docs: fetch regex documentation)
mcp__context7__get-library-docs(python/re)
Edit(/src/email_validator.py)
[SESSION_END]
```

## Compression Results

- **Original session**: ~5,000-10,000 tokens (full conversation)
- **JSONL log**: ~500 tokens (structured events)
- **LLM format**: ~50-100 tokens (ultra-compressed)
- **Compression ratio**: >99% reduction

## Key Benefits

1. **Complete coverage**: All tools, MCP tools, subagents captured
2. **Simple implementation**: One Python script, standard hooks
3. **Minimal overhead**: <100ms per event
4. **Easy consumption**: Agents can read and understand session context instantly
5. **Grep-able**: Simple text format for debugging

## Usage

1. Add hooks to `.claude/settings.json`
2. Create `.claude/hooks/session_logger.py`
3. Sessions automatically logged to `~/.claude/sessions/{session_id}.jsonl`
4. New agents can read session with: `read_session(session_id)`