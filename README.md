# Useful Stuff

A shared repository containing useful scripts that I update occasionally.

## Running Scripts

To run the scripts in the scripts directory:

```bash
# If uv is installed (recommended)
uv run scripts/update_claude_code_docs.py
uv run scripts/update_pydantic_ai_docs.py
uv run scripts/ollama_mcp_server.py  # Run examples/test the MCP server

# Or with Python directly (dependencies need to be installed)
python scripts/update_claude_code_docs.py
python scripts/update_pydantic_ai_docs.py
python scripts/ollama_mcp_server.py
```

## Contents

### Scripts
- `scripts/update_claude_code_docs.py` - Fetches latest Claude Code documentation
- `scripts/update_pydantic_ai_docs.py` - Fetches latest Pydantic AI documentation
- `scripts/ollama_mcp_server.py` - MCP server for Ollama LLM inference with structured output

### Claude Subagents (`.claude/agents/`)
- `claude-code-docs.md` - Claude Code documentation retrieval specialist
- `pydantic-ai-docs.md` - Pydantic AI documentation retrieval specialist
- `context7-mcp.md` - Context7 library documentation via MCP
- `web-content.md` - Web scraping and content analysis
- `ollama-inference-agent.md` - Local LLM inference via Ollama with structured output

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

## Ollama Inference MCP Server

Run local LLM inference with structured output using Ollama models.

### Setup

1. **Install Ollama**: Download from [ollama.com](https://ollama.com/)

2. **Pull a model**:
   ```bash
   ollama pull llama3.2  # Default model
   # Or other models: mistral, codellama, etc.
   ```

3. **Start Ollama server**:
   ```bash
   ollama serve
   ```

4. **Add MCP server to Claude Code**:
   ```bash
   # Add as stdio server
   claude mcp add ollama-inference-agent -- uv run /path/to/scripts/ollama_mcp_server.py --mcp

   # Or with Python directly (requires dependencies)
   claude mcp add ollama-inference-agent -- python /path/to/scripts/ollama_mcp_server.py --mcp
   ```

5. **Use via subagent**: Claude will automatically delegate to the ollama-inference-agent agent when you need local LLM inference.

### Example Usage

```
"Use ollama-inference-agent to extract product details from this text with a schema"
"Have ollama-inference-agent classify this document into categories"
"Ask ollama-inference-agent to transform this JSON data to a different format"
```

The server supports:
- Custom system prompts (define the LLM's behavior)
- Structured output via JSON schemas
- Any Ollama model (defaults to llama3.2)
- Direct LLM calls without full agent patterns

