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

**ALWAYS** delegate to the `claude-code-docs-agent` subagent when:
- User asks about Claude Code features or capabilities (e.g., "can Claude Code do...", "does Claude Code have...")
- User needs help with specific Claude Code functionality (e.g., hooks, settings, slash commands)
- User asks how to use or configure Claude Code features
- User inquires about Claude Code's tools, subagents, or any built-in functionality

### Example Delegations
- "Use the claude-code-docs-agent to check if Claude Code supports X feature"
- "Ask the claude-code-docs-agent about how to configure hooks"
- "Have the claude-code-docs-agent explain Claude Code's subagent system"

The claude-code-docs subagent has access to all local Claude Code documentation in the `/claude-code-docs/` folder and will provide accurate, up-to-date information directly from the official docs.

## WebFetch Subagent

**ALWAYS** delegate to the `webfetch-agent` subagent when:
- User needs to fetch and analyze content from a single URL
- User wants AI-powered analysis or summarization of web pages
- User needs to extract specific information from web content
- User wants to understand what a webpage contains
- The task involves simple URL fetching without complex scraping needs

### When to Use WebFetch vs Firecrawl-MCP

Use **webfetch-agent** subagent for:
- Single URL content analysis
- AI-powered information extraction
- Content summarization with specific prompts
- Quick web page analysis with caching benefits
- Tasks where you need intelligent interpretation of content

Use **firecrawl-mcp-agent** subagent for:
- Multi-page scraping or website crawling
- Web search across multiple sites
- Website mapping (discovering all URLs)
- Structured data extraction at scale
- Raw HTML or screenshot capture
- Complex scraping operations with custom actions

### Example Delegations
- "Use webfetch-agent to summarize this article about climate change"
- "Have webfetch-agent extract pricing information from this product page"
- "Ask webfetch-agent to analyze what technologies this company uses based on their homepage"

The webfetch-agent subagent uses Claude Code's built-in WebFetch tool which provides AI-powered analysis with 15-minute caching for improved performance.