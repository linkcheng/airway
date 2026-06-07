# Implementation Plan: Airway MCP Proxy

**Branch**: `001-airway-mcp-proxy` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-airway-mcp-proxy/spec.md`

## Summary

构建 Airway MCP Proxy——一个通过 MCP 协议将 Bisheng RAG 能力暴露给 Clawith Agent 的
无状态代理层。核心能力：4 个 MCP 工具（rag_query、knowledge_list、knowledge_detail、
knowledge_search）、Bisheng JWT 认证与 Redis 缓存、Clawith→Bisheng 用户映射。
MVP 先实现基于 chunk 搜索的文档检索，后续迭代对接 Bisheng workflow 实现 complete RAG。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: fastmcp>=3.0, httpx>=0.27, pydantic>=2.0, pydantic-settings>=2.0, sqlalchemy[asyncio]>=2.0, asyncpg>=0.29, redis[hiredis]>=5.0, pyyaml>=6.0, cryptography>=42.0, alembic>=1.13

**Storage**: PostgreSQL 15+ (airway_db), Redis 7+ (key prefix: airway:)

**Testing**: pytest + pytest-asyncio + respx (httpx mock)

**Target Platform**: Linux server (Docker)

**Project Type**: MCP server (long-running service)

**Performance Goals**: 10+ concurrent Agent queries, <5s timeout on Bisheng failure

**Constraints**: No Bisheng/Clawith source modifications, no direct Milvus/MinIO access

**Scale/Scope**: MVP: 4 MCP tools, 1 DB table, ~10 files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Open-Closed | PASS | Airway 是独立模块，不修改上游源码 |
| II. Single Responsibility | PASS | 仅做 MCP↔Bisheng 协议转换 |
| III. Dependency Inversion | PASS | 通过 abstract adapter 接口与 Bisheng 交互 |
| IV. Unified User Identity | PASS | Clawith 为主，UserMapping 表做映射 |
| V. Shared Infrastructure | PASS | PostgreSQL/Redis 共享服务器，独立 db/key prefix |
| VI. MVP Iteration | PASS | 4 个工具起步，chunk 搜索先行 |
| VII. Async-First with ORM | PASS | 全 async，SQLAlchemy 2.0 ORM |

**Post-Phase 1 re-check**: All gates still PASS. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-airway-mcp-proxy/
├── plan.md              # This file
├── research.md          # Technology decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Validation guide
├── contracts/
│   └── mcp-tools.md     # MCP tool interface contracts
└── tasks.md             # Task breakdown (by /speckit-tasks)
```

### Source Code (repository root)

```text
airway/
├── __init__.py
├── __main__.py           # Entry point: python -m airway
├── server.py             # FastMCP app + tool registration
├── config.py             # YAML + env config (pydantic-settings)
├── errors.py             # AirwayError + ToolError mapping
├── adapters/
│   ├── __init__.py
│   ├── protocols.py      # BishengAuth + BishengClient Protocol interfaces
│   └── bisheng/
│       ├── __init__.py
│       ├── auth.py       # JWT auth: RSA encrypt + login + token cache
│       └── client.py     # Bisheng v1/v2 HTTP client
├── models/
│   ├── __init__.py
│   └── user_mapping.py   # SQLAlchemy UserMapping model
├── db.py                 # Async engine + session factory
└── migrations/           # Alembic migrations

config.yaml.example       # Sample configuration
pyproject.toml            # Dependencies
alembic.ini               # Alembic config

tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── test_config.py
│   ├── test_auth.py
│   ├── test_client.py
│   └── test_errors.py
└── integration/
    ├── test_server.py
    └── test_tools.py
```

**Structure Decision**: Single project layout. Airway 是一个 Python package (`airway/`)，
作为 MCP server 运行。`tests/` 与 package 同级。

## Complexity Tracking

No constitution violations. No entries needed.
