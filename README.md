# JakeAI Developer Integration & CI/CD Toolkit

This toolkit enables automated pre-deployment sanity checks and multi-model consensus audits before software or website updates hit production.

### Components:
1. `jakeai_audit.py`: Lightweight CLI runner that queries JakeAI's dual-frontier models (Claude 3.5 Sonnet + Perplexity Sonar-Pro) and blocks bad deploys.
2. `.github/workflows/jakeai-audit.yml`: 1-line drop-in GitHub Actions workflow to audit pull requests and commits automatically.
3. `jakeai_mcp_server.py`: Model Context Protocol (MCP) server for Claude Desktop, Cursor, and autonomous agent frameworks.

### Quick Start:
```bash
# Manual CLI Audit on git diff
python jakeai_audit.py --domain mydomain.com

# Audit specific file or text
python jakeai_audit.py --file update_proposal.md --domain mydomain.com
```
