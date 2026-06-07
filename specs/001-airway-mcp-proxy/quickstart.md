# Quickstart: Airway MCP Proxy

**Branch**: `001-airway-mcp-proxy` | **Date**: 2026-06-07

## Prerequisites

- Python 3.12+
- PostgreSQL 15+ (running, accessible)
- Redis 7+ (running, accessible)
- Bisheng backend (running, API accessible)
- uv (package manager)

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure
cp config.yaml.example config.yaml
# Edit config.yaml: set Bisheng URL, credentials, knowledge bases, DB/Redis URLs

# 3. Run database migrations
alembic upgrade head

# 4. Start MCP server (stdio mode - for local testing)
python -m airway

# 5. Start MCP server (HTTP mode - for production)
python -m airway --transport http --host 0.0.0.0 --port 8090
```

## Validation Scenarios

### Scenario 1: List knowledge bases

```bash
# Using MCP inspector or any MCP client
# Call: knowledge_list()
# Expected: list of configured knowledge bases with names and descriptions
```

**Pass criteria**: Returns non-empty list matching config.yaml knowledge_base entries.

### Scenario 2: Query knowledge base

```bash
# Call: rag_query(query="test query", knowledge_base="<name from config>")
# Expected: document chunks with relevance scores
```

**Pass criteria**: Returns chunks with content and source info.

### Scenario 3: Knowledge base detail

```bash
# Call: knowledge_detail(knowledge_base="<name from config>")
# Expected: name, description, document count, status
```

**Pass criteria**: Returns detail matching Bisheng knowledge base info.

### Scenario 4: Search knowledge base

```bash
# Call: knowledge_search(query="keyword", knowledge_base="<name from config>")
# Expected: matching document chunks
```

**Pass criteria**: Returns chunks containing the search keyword.

### Scenario 5: Error handling

```bash
# Call: rag_query(query="test", knowledge_base="nonexistent")
# Expected: "知识库 "nonexistent" 不存在" error
```

**Pass criteria**: Clear error message, no stack trace.

## Health Check

```bash
# HTTP mode only
curl http://localhost:8090/health
# Expected: 200 OK
```
