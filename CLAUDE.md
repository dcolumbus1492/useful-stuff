# CLAUDE.md - Project Guidelines

## MCP Server Usage Policy

**CRITICAL**: All MCP (Model Context Protocol) server operations MUST be delegated to specialized subagents. The primary agent should NEVER directly invoke MCP tools.

### Why This Matters
- Better context management - MCP operations often return large outputs
- Specialized handling - Subagents can be optimized for specific MCP servers
- Clear separation of concerns - Each subagent handles its domain expertly

### How to Use MCP Services

When you need to use any MCP service (e.g., Context7, GitHub, Linear, etc.):

1. **DO NOT** call MCP tools directly
2. **DO** delegate to the appropriate subagent
3. **DO** create new MCP-specialized subagents if needed

### Example Delegations

Instead of directly calling MCP tools, use these patterns:

- "Use the context7-docs agent to fetch React documentation"
- "Have the github-mcp agent review PR #123"
- "Ask the linear-tasks agent to create a new issue"

### Available MCP Subagents

Check `.claude/agents/` for configured MCP subagents. Each should:
- Have a clear name indicating its MCP service
- Include only the specific MCP tools it needs
- Contain domain-specific instructions

Currently configured MCP subagents:
- `firecrawl-mcp` - Handles all Firecrawl MCP operations for web scraping, crawling, searching, and data extraction

Remember: Delegation to subagents is not optional for MCP operations - it's mandatory.

## Claude Code Documentation Subagent

**ALWAYS** delegate to the `claude-code-docs` subagent when:
- User asks about Claude Code features or capabilities (e.g., "can Claude Code do...", "does Claude Code have...")
- User needs help with specific Claude Code functionality (e.g., hooks, settings, slash commands)
- User asks how to use or configure Claude Code features
- User inquires about Claude Code's tools, subagents, or any built-in functionality

### Example Delegations
- "Use the claude-code-docs agent to check if Claude Code supports X feature"
- "Ask the claude-code-docs agent about how to configure hooks"
- "Have the claude-code-docs agent explain Claude Code's subagent system"

The claude-code-docs subagent has access to all local Claude Code documentation in the `/claude-code-docs/` folder and will provide accurate, up-to-date information directly from the official docs.