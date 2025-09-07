# Useful Stuff

A shared repository containing useful scripts that I update occasionally.

## Running Scripts

To run the script in the root directory:

```bash
# If uv is installed (recommended)
uv run update_claude_code_docs.py

# Or with Python directly (`requests` needs to be installed)
python update_claude_code_docs.py
```

## Contents

- `update_claude_code_docs.py` - Script for updating Claude Code documentation
- `.claude/agents/context7-mcp-subagent.md` - Context7 documentation retrieval subagent

## MCP as Subagent Pattern

**Problem**: MCP calls pollute your main conversation with thousands of tokens of noise.

**Solution**: Wrap each MCP server in a dedicated subagent that handles the messy work and returns clean results.

### Quick Setup (Context7 Example)

1. Add MCP server:
   ```bash
   claude mcp add --transport http context7 https://mcp.context7.com/mcp --header "CONTEXT7_API_KEY: YOUR_API_KEY"
   ```

2. Use the provided subagent config in `.claude/agents/context7-mcp-subagent.md`

3. That's it. Claude will automatically delegate documentation requests to the subagent.

### Why It Works

- MCPs provide tool interfaces (what to do)
- Subagents provide task interfaces (how to do it)
- Together: Clean architecture with isolated contexts

