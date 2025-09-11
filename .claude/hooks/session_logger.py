#!/usr/bin/env python3
"""
Claude Code Session Logger

A production-ready session logger that captures all Claude Code events into a 
compressed JSONL format. Designed for minimal overhead and maximum reliability.

Author: Claude Code Session Logger
Version: 1.0.0
"""

import json
import sys
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import fcntl

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
SESSION_DIR = PROJECT_ROOT / '.claude' / 'sessions'
LOG_DIR = PROJECT_ROOT / '.claude' / 'logs'
MAX_TARGET_LENGTH = 150
MAX_PROMPT_LENGTH = 120
DEBUG_MODE = os.environ.get('SESSION_LOGGER_DEBUG', '').lower() == 'true'

# Ensure directories exist
SESSION_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

class SessionLogger:
    """Main session logger class with robust error handling and efficient processing."""
    
    # Tool parameter mappings
    TOOL_PARAM_MAP = {
        # File operations
        'Read': 'file_path',
        'Write': 'file_path',
        'Edit': 'file_path',
        'MultiEdit': 'file_path',
        'NotebookEdit': 'notebook_path',
        
        # Command execution
        'Bash': 'command',
        'BashOutput': 'bash_id',
        'KillBash': 'shell_id',
        
        # Search operations
        'Grep': lambda inp: f"{inp.get('pattern', '')} in {inp.get('path', '.')}",
        'Glob': lambda inp: f"{inp.get('pattern', '')} in {inp.get('path', '.')}",
        
        # Agent operations
        'Task': lambda inp: f"{inp.get('subagent_type', 'agent')}: {inp.get('description', '')}",
        
        # Web operations
        'WebFetch': 'url',
        
        # Todo management
        'TodoWrite': lambda inp: f"{len(inp.get('todos', []))} todos",
        
        # Special operations
        'ExitPlanMode': lambda inp: inp.get('plan', '')[:50] + '...' if inp.get('plan', '') else '',
    }
    
    def __init__(self):
        self.session_files: Dict[str, Path] = {}  # Cache session_id -> file mapping
        self.error_log = LOG_DIR / 'session_logger_errors.log'
        self.index_file = SESSION_DIR / '.session_index.json'
        self._load_session_index()
        
    def log_debug(self, message: str) -> None:
        """Log debug messages if debug mode is enabled."""
        if DEBUG_MODE:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[SESSION_LOGGER_DEBUG {timestamp}] {message}", file=sys.stderr)
    
    def log_error(self, error: Exception, context: str = "") -> None:
        """Log errors to error file and stderr."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        error_msg = f"[{timestamp}] {context}: {type(error).__name__}: {str(error)}\n"
        error_msg += f"Traceback:\n{traceback.format_exc()}\n"
        
        # Log to stderr
        print(f"[SESSION_LOGGER_ERROR] {error_msg}", file=sys.stderr)
        
        # Log to file
        try:
            with open(self.error_log, 'a') as f:
                f.write(error_msg + "\n" + "-"*80 + "\n")
        except:
            pass  # Fail silently if we can't write to error log
    
    def _load_session_index(self) -> None:
        """Load the session index mapping session_ids to files."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    # Convert to Path objects
                    self.session_files = {
                        sid: SESSION_DIR / fname 
                        for sid, fname in data.get('sessions', {}).items()
                    }
                    self.next_index = data.get('next_index', 1)
            except Exception as e:
                self.log_error(e, "Failed to load session index")
                self.session_files = {}
                self.next_index = 1
        else:
            self.session_files = {}
            self.next_index = 1
    
    def _save_session_index(self) -> None:
        """Save the session index with file locking for concurrency."""
        try:
            # Prepare data
            data = {
                'sessions': {
                    sid: path.name 
                    for sid, path in self.session_files.items()
                },
                'next_index': self.next_index
            }
            
            # Write with atomic operation
            temp_file = self.index_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                # Lock file during write
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename
            temp_file.rename(self.index_file)
            
        except Exception as e:
            self.log_error(e, "Failed to save session index")
    
    def get_session_file(self, session_id: str) -> Path:
        """Get or create session file with stable naming."""
        # Check if we already have a file for this session
        if session_id in self.session_files:
            return self.session_files[session_id]
        
        # Create new file with ordered index
        index = str(self.next_index).zfill(4)
        filename = f"{index}_{session_id}.jsonl"
        session_file = SESSION_DIR / filename
        
        # Update tracking
        self.session_files[session_id] = session_file
        self.next_index += 1
        
        # Save index
        self._save_session_index()
        
        self.log_debug(f"Created new session file: {filename}")
        return session_file
    
    def extract_target(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Extract the most relevant parameter from tool input.
        Handles various tool types and edge cases gracefully.
        """
        if not tool_input:
            return ""
        
        try:
            # Handle MCP tools
            if tool_name.startswith("mcp__"):
                return self._extract_mcp_target(tool_name, tool_input)
            
            # Get mapping for this tool
            mapping = self.TOOL_PARAM_MAP.get(tool_name)
            
            if mapping is None:
                # Unknown tool - try to extract first meaningful string
                return self._extract_default_target(tool_input)
            
            if callable(mapping):
                # Custom extraction function
                result = mapping(tool_input)
                return self._truncate_target(str(result))
            
            # Simple parameter mapping
            value = tool_input.get(mapping, "")
            
            # Special handling for certain tools
            if tool_name == "Bash" and value:
                # Clean up bash commands
                value = self._clean_bash_command(value)
            elif tool_name in ["Read", "Write", "Edit", "MultiEdit"] and value:
                # Simplify file paths
                value = self._simplify_path(value)
            
            return self._truncate_target(str(value))
            
        except Exception as e:
            self.log_error(e, f"Error extracting target for {tool_name}")
            return "error"
    
    def _extract_mcp_target(self, _tool_name: str, tool_input: Dict[str, Any]) -> str:
        """Extract target for MCP tools with intelligent parameter detection."""
        # Common MCP parameter patterns
        priority_params = ['url', 'query', 'path', 'name', 'id', 'content', 'message', 'prompt']
        
        # Check priority parameters first
        for param in priority_params:
            if param in tool_input:
                value = str(tool_input[param])
                if value and not value.isspace():
                    return self._truncate_target(value)
        
        # Fall back to first non-empty string value
        for _, value in tool_input.items():
            if isinstance(value, str) and value and not value.isspace():
                return self._truncate_target(value)
        
        # Try first list item if it's a string
        for value in tool_input.values():
            if isinstance(value, list) and value and isinstance(value[0], str):
                return self._truncate_target(value[0])
        
        return f"mcp_call({len(tool_input)} params)"
    
    def _extract_default_target(self, tool_input: Dict[str, Any]) -> str:
        """Extract target for unknown tools."""
        # Try common parameter names
        for param in ['file_path', 'path', 'command', 'url', 'query', 'name', 'id']:
            if param in tool_input:
                return self._truncate_target(str(tool_input[param]))
        
        # Return first string value
        for value in tool_input.values():
            if isinstance(value, str) and value:
                return self._truncate_target(value)
        
        return "unknown"
    
    def _clean_bash_command(self, command: str) -> str:
        """Clean and simplify bash commands."""
        # Remove excessive whitespace
        command = ' '.join(command.split())
        
        # Remove common prefixes that don't add value
        prefixes_to_remove = [
            'python3 -m ',
            'python -m ',
            'npm run ',
            'yarn ',
        ]
        for prefix in prefixes_to_remove:
            if command.startswith(prefix):
                command = command[len(prefix):]
                break
        
        return command
    
    def _simplify_path(self, path: str) -> str:
        """Simplify file paths for better readability."""
        # Convert to Path object for normalization
        try:
            path_obj = Path(path)
            
            # If path is under project root, make it relative
            if path_obj.is_absolute():
                try:
                    rel_path = path_obj.relative_to(PROJECT_ROOT)
                    return str(rel_path)
                except ValueError:
                    pass
            
            # Simplify home directory
            home = Path.home()
            if path_obj.is_absolute():
                try:
                    rel_home = path_obj.relative_to(home)
                    return f"~/{rel_home}"
                except ValueError:
                    pass
            
            return str(path_obj)
        except:
            return path
    
    def _truncate_target(self, target: str) -> str:
        """Truncate target string to maximum length."""
        if len(target) <= MAX_TARGET_LENGTH:
            return target
        return target[:MAX_TARGET_LENGTH-3] + "..."
    
    def log_event(self, session_id: str, event_type: str, 
                  target: str = "", status: str = "ok") -> None:
        """
        Log a single event to the session file.
        Thread-safe and handles errors gracefully.
        """
        try:
            event = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "type": event_type,
                "target": target,
                "status": status
            }
            
            session_file = self.get_session_file(session_id)
            
            # Atomic append operation
            with open(session_file, 'a') as f:
                json.dump(event, f, ensure_ascii=False, separators=(',', ':'))
                f.write('\n')
                f.flush()  # Ensure write is committed
            
            self.log_debug(f"Logged event: {event_type}({target[:50]}...)")
            
        except Exception as e:
            self.log_error(e, f"Failed to log event {event_type}")

def main():
    """Main entry point for hook execution."""
    logger = SessionLogger()
    
    try:
        # Read input from stdin
        if sys.stdin.isatty():
            logger.log_debug("No input on stdin, exiting")
            sys.exit(0)
        
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            logger.log_debug("Empty input, exiting")
            sys.exit(0)
        
        # Parse JSON input
        try:
            data = json.loads(raw_input)
        except json.JSONDecodeError as e:
            logger.log_error(e, "Failed to parse JSON input")
            sys.exit(0)
        
        # Get action from command line argument
        action = sys.argv[1] if len(sys.argv) > 1 else "unknown"
        session_id = data.get("session_id", "unknown")
        
        logger.log_debug(f"Processing action: {action} for session: {session_id}")
        
        # Route to appropriate handler
        if action == "session_start":
            source = data.get("source", "unknown")
            logger.log_event(session_id, "SESSION_START", source)
            
        elif action == "user_prompt":
            prompt = data.get("prompt", "")
            # Clean and truncate prompt
            prompt_clean = ' '.join(prompt.split())[:MAX_PROMPT_LENGTH]
            if len(prompt) > MAX_PROMPT_LENGTH:
                prompt_clean += "..."
            logger.log_event(session_id, "USER", prompt_clean)
            
        elif action == "tool_use":
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", {})
            target = logger.extract_target(tool_name, tool_input)
            logger.log_event(session_id, tool_name, target)
            
        elif action == "tool_result":
            # Log only errors to avoid duplication
            tool_name = data.get("tool_name", "unknown")
            tool_response = data.get("tool_response", {})
            
            # Check for error in response
            error_detected = False
            if isinstance(tool_response, dict):
                error_detected = bool(tool_response.get("error"))
            elif isinstance(tool_response, str):
                error_detected = "error" in tool_response.lower()
            
            if error_detected:
                tool_input = data.get("tool_input", {})
                target = logger.extract_target(tool_name, tool_input)
                logger.log_event(session_id, tool_name, target, "error")
            
        elif action == "subagent_stop":
            # Extract subagent info if available
            stop_info = "completed"
            if "stop_hook_active" in data:
                stop_info = "active" if data["stop_hook_active"] else "inactive"
            logger.log_event(session_id, "SUBAGENT_STOP", stop_info)
            
        elif action == "session_end":
            reason = data.get("reason", "unknown")
            logger.log_event(session_id, "SESSION_END", reason)
        
        else:
            logger.log_debug(f"Unknown action: {action}")
        
    except Exception as e:
        logger.log_error(e, "Unhandled exception in main")
    
    # Always exit successfully to avoid blocking hooks
    sys.exit(0)

if __name__ == "__main__":
    main()