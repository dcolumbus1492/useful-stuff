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
- `web-content` - Comprehensive web content specialist that intelligently handles all web-related tasks, from simple URL analysis to complex scraping, crawling, and searching

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

## Web Content Subagent

**ALWAYS** delegate to the `web-content` subagent when:
- User needs to fetch, analyze, or extract content from any URL
- User wants to search the web for information
- User needs to scrape data from websites
- User wants to crawl multiple pages or entire websites
- User needs screenshots or raw HTML from web pages
- User wants to discover all URLs on a website
- User needs AI-powered analysis or summarization of web content
- ANY task involving web content retrieval or analysis

### Intelligent Tool Selection

The web-content subagent automatically selects the most appropriate tool:

**Simple AI Analysis** (via WebFetch):
- Single URL content analysis
- AI-powered interpretation or summary
- Quick analysis with 15-minute caching
- Natural language information extraction

**Advanced Operations** (via Firecrawl MCP):
- Multi-page scraping or crawling
- Web search across multiple sites
- Website mapping and URL discovery
- Structured data extraction at scale
- Screenshots and raw HTML capture
- Complex scraping with custom actions

### Example Delegations
- "Use web-content agent to summarize this article"
- "Have web-content agent search for recent AI research papers"
- "Ask web-content agent to scrape all product prices from this e-commerce site"
- "Use web-content agent to map the structure of docs.example.com"
- "Have web-content agent extract contact information from this webpage"

The web-content subagent is your one-stop solution for ALL web-related tasks, intelligently choosing between simple AI analysis and advanced scraping capabilities based on the specific needs of each request.