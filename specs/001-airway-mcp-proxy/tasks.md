# Tasks: Airway MCP Proxy

**Input**: Design documents from `/specs/001-airway-mcp-proxy/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/mcp-tools.md

**Tests**: TDD 模式，测试任务写在实现之前。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Initialize Python project with pyproject.toml (dependencies: fastmcp>=3.0, httpx>=0.27, pydantic>=2.0, pydantic-settings>=2.0, sqlalchemy[asyncio]>=2.0, asyncpg>=0.29, redis[hiredis]>=5.0, pyyaml>=6.0, cryptography>=42.0, alembic>=1.13, pytest>=8.0, pytest-asyncio>=0.23, respx>=0.21, ruff)
- [x] T002 Create airway/ package structure: airway/__init__.py, airway/__main__.py, airway/adapters/__init__.py, airway/adapters/bisheng/__init__.py, airway/models/__init__.py, tests/__init__.py, tests/unit/__init__.py, tests/integration/__init__.py
- [x] T003 [P] Create config.yaml.example with Bisheng URL, admin credentials, knowledge base mappings, PostgreSQL URL, Redis URL, server host/port
- [x] T004 [P] Implement config module in airway/config.py using pydantic-settings with YAML loading and env var override
- [x] T005 [P] Implement error types in airway/errors.py: AirwayError(code, message) and helper to convert to ToolError; define BishengAuth Protocol (login, get_token) and BishengClient Protocol (list_knowledge, get_knowledge, search_chunks) in airway/adapters/protocols.py
- [x] T006 [P] Configure pytest in pyproject.toml: asyncio_mode=auto, testpaths=["tests"]
- [x] T007 [P] Configure Alembic: alembic.ini and airway/migrations/env.py with async engine support

**Checkpoint**: Project structure ready, config loads, errors defined

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**WARNING**: No user story work can begin until this phase is complete

- [x] T008 Write failing test for Bisheng auth: test RSA public key fetch, test password encryption, test login, test token cache in tests/unit/test_auth.py
- [x] T009 Implement Bisheng auth adapter in airway/adapters/bisheng/auth.py: fetch RSA public key from `/api/v1/user/public_key`, encrypt password (MD5 → RSA → base64), login via `POST /api/v1/user/login`, cache JWT token in Redis with TTL, auto-refresh before expiry
- [x] T010 Write failing test for Bisheng HTTP client: test knowledge list, test knowledge detail, test chunk search, test error mapping in tests/unit/test_client.py
- [x] T011 Implement Bisheng HTTP client in airway/adapters/bisheng/client.py: async httpx client with timeout=5.0s, connect_timeout=3.0s, implement BishengClient Protocol methods for knowledge list (GET /api/v2/knowledge), knowledge detail (GET /api/v1/knowledge/info), chunk search (GET /api/v1/knowledge/chunk), unified error handling mapping Bisheng status_codes to AirwayError
- [x] T012 Implement async database setup in airway/db.py: async engine factory, AsyncSession maker, connection from config
- [x] T013 Implement UserMapping model in airway/models/user_mapping.py per data-model.md schema

**Checkpoint**: Foundation ready - auth, client, DB all working with passing tests

---

## Phase 3: User Story 1 - Agent 查询知识库 (Priority: P1) MVP

**Goal**: Agent calls rag_query tool, gets document chunks from Bisheng knowledge base

**Independent Test**: MCP client calls rag_query with test query, verifies returned chunks contain relevant content

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T014 [US1] Write failing test for rag_query tool in tests/unit/test_server.py: mock Bisheng client, verify tool registration, verify input validation (empty query, missing kb, top_k out of range <1 or >20), verify chunk formatting in output

### Implementation for User Story 1

- [x] T015 [US1] Implement FastMCP server in airway/server.py: create FastMCP("airway"), register rag_query tool with input schema from contracts/mcp-tools.md, wire to Bisheng client, handle errors via AirwayError→ToolError, add health check custom_route
- [x] T016 [US1] Implement entry point in airway/__main__.py: load config, init DB engine, init Bisheng auth+client, run MCP server; use sys.argv for transport selection (--transport http, default stdio)
- [x] T017 [US1] Implement knowledge base name→ID resolution in airway/server.py: lookup config.knowledge_bases mapping, raise AirwayError if name not found

**Checkpoint**: rag_query tool works end-to-end via MCP client

---

## Phase 4: User Story 2 - 浏览知识库 (Priority: P2)

**Goal**: Agent lists knowledge bases and views details

**Independent Test**: MCP client calls knowledge_list, verifies returned list matches config; calls knowledge_detail, verifies detail info

### Tests for User Story 2

- [x] T018 [P] [US2] Write failing test for knowledge_list and knowledge_detail tools in tests/unit/test_server.py: mock Bisheng client list/detail responses, verify output formatting

### Implementation for User Story 2

- [x] T019 [US2] Add knowledge_list tool to airway/server.py: call Bisheng client list, format output per contracts/mcp-tools.md
- [x] T020 [US2] Add knowledge_detail tool to airway/server.py: resolve kb name→ID, call Bisheng client detail, format output per contracts/mcp-tools.md

**Checkpoint**: knowledge_list and knowledge_detail tools both work independently

---

## Phase 5: User Story 3 - 用户身份自动映射 (Priority: P3)

**Goal**: Clawith users auto-map to Bisheng users on first tool use

**Independent Test**: New Clawith user ID triggers mapping creation in DB, subsequent calls use existing mapping

### Tests for User Story 3

- [x] T021 [P] [US3] Write failing test for user mapping in tests/unit/test_server.py: test auto-create mapping on first call, test reuse existing mapping, test Bisheng user creation call

### Implementation for User Story 3

- [x] T022 [US3] Add user mapping logic in airway/server.py: on each tool call, check DB for Clawith user→Bisheng user mapping, if missing call `POST /api/v1/user/regist` to create Bisheng user (using RSA-encrypted password from auth.py), save mapping to DB
- [x] T023 [US3] Add Alembic migration for user_mappings table in airway/migrations/versions/

**Checkpoint**: User mapping auto-creates and persists across tool calls

---

## Phase 6: User Story 4 - 搜索知识库文档片段 (Priority: P4)

**Goal**: Agent searches knowledge base by keyword, gets matching chunks

**Independent Test**: MCP client calls knowledge_search with keyword, verifies chunks contain the keyword

### Tests for User Story 4

- [x] T024 [P] [US4] Write failing test for knowledge_search tool in tests/unit/test_server.py: mock Bisheng chunk search, verify keyword-based results formatting

### Implementation for User Story 4

- [x] T025 [US4] Add knowledge_search tool to airway/server.py: resolve kb name→ID, call Bisheng client chunk search with keyword, format output per contracts/mcp-tools.md

**Checkpoint**: All 4 MCP tools work independently and together

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T026 Write integration tests in tests/integration/test_server.py: test all 4 tools with mocked Bisheng backend, test both transport modes (stdio and streamable-http), test concurrent requests
- [x] T027 [P] Write config tests in tests/unit/test_config.py: test YAML loading, test env var override, test missing fields validation
- [x] T028 Run ruff check and fix all lint issues
- [x] T029 Validate quickstart.md scenarios end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1) → US2 (P2) → US3 (P3) → US4 (P4) recommended order
  - US2 and US4 can be parallel (independent tools)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational only - no cross-story deps
- **US2 (P2)**: Depends on Foundational only - can run parallel with US1 tools
- **US3 (P3)**: Depends on Foundational + DB migration (T023) - needs user_mappings table
- **US4 (P4)**: Depends on Foundational only - can run parallel with US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Server tools before mapping logic
- Core implementation before integration testing

### Parallel Opportunities

- T003, T004, T005, T006, T007 can all run in parallel (Phase 1)
- T009 and T011 can run in parallel after T008 and T010 pass
- T018 and T024 can run in parallel (test tasks for US2 and US4)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T013)
3. Complete Phase 3: User Story 1 (T014-T017)
4. **STOP and VALIDATE**: Test rag_query independently via MCP client
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → rag_query works (MVP!)
3. Add US2 → knowledge browsing works
4. Add US3 → user mapping works
5. Add US4 → keyword search works
6. Polish → production-ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
