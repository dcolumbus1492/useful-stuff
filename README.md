# Useful Stuff

A shared repository containing useful scripts that I update occasionally.

## Running Scripts

To run the scripts in the scripts directory:

```bash
# If uv is installed (recommended)
uv run scripts/update_claude_code_docs.py

# Or with Python directly (`requests` needs to be installed)
python scripts/update_claude_code_docs.py
```

## Contents

### Scripts
- `scripts/update_claude_code_docs.py` - Fetches latest Claude Code documentation

### Claude Subagents (`.claude/agents/`)
- `claude-code-docs.md` - Claude Code documentation retrieval specialist
- `context7-mcp.md` - Context7 library documentation via MCP
- `web-content.md` - Web scraping and content analysis

### Documentation
- `CLAUDE.md` - Project guidelines and MCP usage policy
- `DOCS/` - Various documentation files

## MCP as Subagent Pattern

**Problem**: MCP calls pollute your main conversation with thousands of tokens of noise.

**Solution**: Wrap each MCP server in a dedicated subagent that handles the messy work and returns clean results.

### Quick Setup (Context7 Example)

1. Add MCP server:
   ```bash
   claude mcp add --transport http context7 https://mcp.context7.com/mcp --header "CONTEXT7_API_KEY: YOUR_API_KEY"
   ```

2. Use the provided subagent config in `.claude/agents/context7-mcp.md`

3. That's it. Claude will automatically delegate documentation requests to the subagent.

### Why It Works

- MCPs provide tool interfaces (what to do)
- Subagents provide task interfaces (how to do it)
- Together: Clean architecture with isolated contexts

