#!/usr/bin/env python3
"""
Claude Code Session Reader

Reads session logs and formats them for LLM consumption with extreme compression.
Can output in various formats optimized for different use cases.

Author: Claude Code Session Logger
Version: 1.0.0
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict
import argparse

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
SESSION_DIR = PROJECT_ROOT / '.claude' / 'sessions'

class SessionReader:
    """Read and format session logs for various consumption patterns."""
    
    # Event type display mappings for ultra-compressed format
    EVENT_DISPLAY_MAP = {
        'SESSION_START': '[START]',
        'SESSION_END': '[END]',
        'SUBAGENT_STOP': '[SUBAGENT_DONE]',
        'USER': 'USER:',
        'Notification': '[NOTIFY]',
    }
    
    # Tool groupings for summarization
    TOOL_GROUPS = {
        'file_ops': ['Read', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit'],
        'search_ops': ['Grep', 'Glob'],
        'exec_ops': ['Bash', 'BashOutput', 'KillBash'],
        'agent_ops': ['Task'],
        'web_ops': ['WebFetch'],
        'mcp_ops': [],  # Filled dynamically with mcp__* tools
    }
    
    def __init__(self, session_file: Path):
        """Initialize reader with a session file."""
        self.session_file = session_file
        self.events = self._load_events()
        
    def _load_events(self) -> List[Dict[str, Any]]:
        """Load and parse all events from the session file."""
        events = []
        if not self.session_file.exists():
            return events
            
        try:
            with open(self.session_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON at line {line_num}: {e}", file=sys.stderr)
                        continue
        except Exception as e:
            print(f"Error reading session file: {e}", file=sys.stderr)
            
        return events
    
    def get_ultra_compressed(self) -> str:
        """
        Get ultra-compressed format for LLM consumption.
        Optimized for minimal token usage while maintaining comprehension.
        """
        lines = []
        
        for event in self.events:
            event_type = event.get('type', 'unknown')
            target = event.get('target', '')
            status = event.get('status', 'ok')
            
            # Don't skip any events in ultra-compressed format
            
            # Format based on event type
            if event_type in self.EVENT_DISPLAY_MAP:
                if event_type == 'USER':
                    lines.append(f"{self.EVENT_DISPLAY_MAP[event_type]} {target}")
                else:
                    lines.append(self.EVENT_DISPLAY_MAP[event_type])
            else:
                # Tool usage - ultra compressed
                if status == 'error':
                    lines.append(f"{event_type}({target}) ❌")
                else:
                    lines.append(f"{event_type}({target})")
        
        return '\n'.join(lines)
    
    def get_structured_summary(self) -> Dict[str, Any]:
        """
        Get a structured summary of the session.
        Useful for analytics and detailed session understanding.
        """
        summary = {
            'session_id': self.session_file.stem,
            'duration': None,
            'total_events': len(self.events),
            'user_prompts': [],
            'tools_used': defaultdict(int),
            'errors': [],
            'files_touched': set(),
            'commands_run': [],
            'agents_launched': [],
            'mcp_calls': []
        }
        
        start_time = None
        end_time = None
        
        for event in self.events:
            event_type = event.get('type', 'unknown')
            target = event.get('target', '')
            status = event.get('status', 'ok')
            timestamp = event.get('ts', '')
            
            # Track timestamps
            if timestamp:
                try:
                    ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if event_type == 'SESSION_START':
                        start_time = ts
                    elif event_type == 'SESSION_END':
                        end_time = ts
                except:
                    pass
            
            # Categorize events
            if event_type == 'USER':
                summary['user_prompts'].append(target)
            elif event_type in ['Read', 'Write', 'Edit', 'MultiEdit']:
                summary['files_touched'].add(target)
                summary['tools_used'][event_type] += 1
            elif event_type == 'Bash':
                summary['commands_run'].append(target)
                summary['tools_used'][event_type] += 1
            elif event_type == 'Task':
                summary['agents_launched'].append(target)
                summary['tools_used'][event_type] += 1
            elif event_type.startswith('mcp__'):
                summary['mcp_calls'].append(f"{event_type}: {target}")
                summary['tools_used']['MCP'] += 1
            elif event_type not in ['SESSION_START', 'SESSION_END', 'SUBAGENT_STOP']:
                summary['tools_used'][event_type] += 1
            
            # Track errors
            if status == 'error':
                summary['errors'].append(f"{event_type}({target})")
        
        # Calculate duration
        if start_time and end_time:
            duration = end_time - start_time
            summary['duration'] = str(duration)
        
        # Convert sets to lists for JSON serialization
        summary['files_touched'] = sorted(list(summary['files_touched']))
        summary['tools_used'] = dict(summary['tools_used'])
        
        return summary
    
    def get_narrative_format(self) -> str:
        """
        Get a narrative format that's more human-readable.
        Good for session reports and documentation.
        """
        narrative = []
        summary = self.get_structured_summary()
        
        narrative.append(f"# Session Report: {summary['session_id']}")
        narrative.append("")
        
        if summary['duration']:
            narrative.append(f"**Duration**: {summary['duration']}")
        narrative.append(f"**Total Events**: {summary['total_events']}")
        narrative.append("")
        
        if summary['user_prompts']:
            narrative.append("## User Requests")
            for i, prompt in enumerate(summary['user_prompts'], 1):
                narrative.append(f"{i}. {prompt}")
            narrative.append("")
        
        if summary['tools_used']:
            narrative.append("## Tools Used")
            for tool, count in sorted(summary['tools_used'].items()):
                narrative.append(f"- {tool}: {count} time(s)")
            narrative.append("")
        
        if summary['files_touched']:
            narrative.append("## Files Modified")
            for file in summary['files_touched']:
                narrative.append(f"- {file}")
            narrative.append("")
        
        if summary['commands_run']:
            narrative.append("## Commands Executed")
            for cmd in summary['commands_run']:
                narrative.append(f"- `{cmd}`")
            narrative.append("")
        
        if summary['errors']:
            narrative.append("## Errors Encountered")
            for error in summary['errors']:
                narrative.append(f"- {error}")
            narrative.append("")
        
        return '\n'.join(narrative)
    
    def get_timeline_format(self) -> str:
        """
        Get a timeline format showing events with timestamps.
        Useful for debugging and understanding event sequence.
        """
        lines = []
        
        for event in self.events:
            timestamp = event.get('ts', 'unknown')
            event_type = event.get('type', 'unknown')
            target = event.get('target', '')
            status = event.get('status', 'ok')
            
            # Parse timestamp for better display
            try:
                ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = ts.strftime('%H:%M:%S')
            except:
                time_str = 'unknown'
            
            # Format line
            status_indicator = ' ❌' if status == 'error' else ''
            
            if event_type in self.EVENT_DISPLAY_MAP:
                if target:
                    lines.append(f"{time_str} {self.EVENT_DISPLAY_MAP[event_type]} {target}{status_indicator}")
                else:
                    lines.append(f"{time_str} {self.EVENT_DISPLAY_MAP[event_type]}{status_indicator}")
            else:
                lines.append(f"{time_str} {event_type}({target}){status_indicator}")
        
        return '\n'.join(lines)

def find_latest_session() -> Optional[Path]:
    """Find the most recent session file."""
    if not SESSION_DIR.exists():
        return None
    
    session_files = list(SESSION_DIR.glob('*.jsonl'))
    if not session_files:
        return None
    
    # Sort by modification time, most recent first
    return max(session_files, key=lambda f: f.stat().st_mtime)

def list_sessions() -> List[Tuple[str, str]]:
    """List all available sessions with their timestamps."""
    if not SESSION_DIR.exists():
        return []
    
    sessions = []
    for session_file in SESSION_DIR.glob('*.jsonl'):
        # Extract timestamp from filename
        parts = session_file.stem.split('_', 2)
        if len(parts) >= 3:
            date_str = parts[0]
            time_str = parts[1]
            session_id = parts[2]
            
            try:
                # Format timestamp for display
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M")
                display_time = dt.strftime("%Y-%m-%d %H:%M")
                sessions.append((session_file.stem, f"{display_time} - {session_id}"))
            except:
                sessions.append((session_file.stem, session_file.stem))
    
    return sorted(sessions, reverse=True)

def main():
    parser = argparse.ArgumentParser(description='Read Claude Code session logs')
    parser.add_argument('session', nargs='?', help='Session ID or "latest" for most recent')
    parser.add_argument('-f', '--format', choices=['compressed', 'summary', 'narrative', 'timeline'],
                        default='compressed', help='Output format')
    parser.add_argument('-l', '--list', action='store_true', help='List all sessions')
    
    args = parser.parse_args()
    
    # List sessions if requested
    if args.list:
        sessions = list_sessions()
        if not sessions:
            print("No sessions found")
            return
        
        print("Available sessions:")
        for session_id, display in sessions:
            print(f"  {display}")
        return
    
    # Find session file
    if not args.session or args.session == 'latest':
        session_file = find_latest_session()
        if not session_file:
            print("No sessions found")
            sys.exit(1)
    else:
        # Try to find matching session
        if SESSION_DIR.exists():
            # First try exact match
            session_file = SESSION_DIR / f"{args.session}.jsonl"
            if not session_file.exists():
                # Try partial match
                matches = list(SESSION_DIR.glob(f"*{args.session}*.jsonl"))
                if matches:
                    session_file = matches[0]
                else:
                    print(f"Session not found: {args.session}")
                    sys.exit(1)
        else:
            print("No sessions directory found")
            sys.exit(1)
    
    # Read and format session
    reader = SessionReader(session_file)
    
    if args.format == 'compressed':
        print(reader.get_ultra_compressed())
    elif args.format == 'summary':
        summary = reader.get_structured_summary()
        print(json.dumps(summary, indent=2))
    elif args.format == 'narrative':
        print(reader.get_narrative_format())
    elif args.format == 'timeline':
        print(reader.get_timeline_format())

if __name__ == "__main__":
    main()