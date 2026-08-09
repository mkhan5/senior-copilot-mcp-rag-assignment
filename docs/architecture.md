# Architecture Documentation

## Overview

The Maintenance and Work-Order Intelligence Copilot is a multi-layered system that integrates alarm management, maintenance history (CMMS), and document knowledge (RAG) through Model Context Protocol (MCP) servers. The architecture enforces strict separation of concerns: the copilot orchestrator never calls source APIs directly—it communicates exclusively through MCP servers.

## System Layers

### 1. Frontend Layer (Port 3000)
- **Technology**: React + TypeScript + Vite
- **Features**: Chat interface with markdown rendering, three side-panel tabs:
  - 📄 **Citations**: Document sources with relevance scores
  - 🖥️ **MCP Trace**: Real-time MCP tool calls (tool name, input, output, timestamp)
  - 📋 **Query Plan**: LangGraph execution plan with routing decisions
- **Confidence Meter**: 0-100% based on retrieval and data completeness

### 2. Copilot Backend Orchestration (Port 8002)
- **Technology**: FastAPI + LangGraph
- **Workflow**: 7-node state machine:
  1. `detect_intent` — Gemini 2.5 Flash extracts intent, assets, time range, routing flags
  2. `discover_mcp_tools` — Lists tools from both MCP servers via `list_tools()`
  3. `plan_mcp_execution` — Generates query plan with conditional routing
  4. `execute_alarm_tools` — Queries Alarm MCP (conditional)
  5. `execute_maintenance_tools` — Queries Maintenance MCP (conditional)
  6. `query_rag` — Retrieves document knowledge (conditional)
  7. `synthesize_answer` — Gemini 2.5 Flash combines all sources into grounded answer
- **Session Store**: In-memory multi-turn conversation context (last 20 turns)
- **RAG Client**: Integrated `RetrievalService` for document queries

### 3. MCP Client Layer (In Backend)
- **Transport**: Streamable HTTP (`streamablehttp_client`)
- **Clients**: Two independent clients:
  - Alarm MCP Client → `http://alarm-mcp:9000/mcp`
  - Maintenance MCP Client → `http://maintenance-mcp:9001/mcp`
- **Features**: Tool discovery (`list_tools`), schema-aware invocation (`call_tool`), retry/error handling, LangSmith tracing (`@traceable`)

### 4. MCP Server Layer
#### Alarm Management MCP Server (Port 9000)
- **Framework**: FastMCP with Streamable HTTP Transport
- **Tools (13)**: `search_assets`, `get_asset_metadata`, `get_alarms`, `get_alarm_by_id`, `get_alarm_summary`, `get_alarm_trends`, `get_alarm_correlation`, `get_flood_analysis`, `get_rationalization_candidates`, `get_priority_score`, `get_operator_recommendations`
- **Resilience**: Retry (max 3), 30s timeout, Bearer token auth, trace header propagation
- **Health**: `/health` endpoint checks upstream Alarm API

#### Maintenance CMMS MCP Server (Port 9001)
- **Framework**: FastMCP with Streamable HTTP Transport
- **Tools (7)**: `search_assets`, `get_asset_metadata`, `get_work_orders`, `get_maintenance_logs`, `get_asset_work_order_summary`, `get_asset_maintenance_summary`, `get_spare_parts`
- **Resilience**: Retry (max 3), 30s timeout
- **Health**: `/health` endpoint checks upstream CMMS API

### 5. Source Systems
#### Alarm API Simulator (Port 8000)
- **Technology**: FastAPI, Postman spec compliant
- **Endpoints**: 11 endpoints including `/assets/search`, `/alarms`, `/alarms/summary`, `/alarms/correlation`, `/alarms/flood-analysis`, `/alarms/priority-score`, `/recommendations/operator-actions`
- **Auth**: Bearer token (`demo-token`), trace header propagation

#### Maintenance CMMS API (Port 8001)
- **Technology**: FastAPI + SQLite (pre-seeded demo data)
- **Endpoints**: `/assets`, `/work-orders`, `/maintenance-logs`, `/assets/{id}/work-order-summary`, `/assets/{id}/maintenance-summary`, `/spare-parts`

### 6. RAG Pipeline
#### Ingestion (Batch Job)
- **Documents**: 5 markdown files (equipment manuals, procedures, checklists, spare parts guidance)
- **Loader**: Markdown, Text, PDF support
- **Splitter**: `RecursiveCharacterTextSplitter` (chunk_size=500, overlap=50)
- **Embedder**: `SentenceTransformer` `all-MiniLM-L6-v2`
- **Vector Store**: ChromaDB PersistentClient, cosine similarity, collection: `maintenance_docs`
- **Metadata**: Auto-extracted `asset_id`, `asset_name`, `doc_type`, `source`

#### Retrieval (Real-time)
- **Service**: `RetrievalService` with vector search + metadata filters (`asset_id`, `doc_type`)
- **Prompt Guard**: Injection detection (12 patterns)
- **Generation**: Gemini 2.5 Flash with grounded prompt (citation IDs required)
- **Citations**: Structured output with `citation_id`, `source`, `asset`, `score`, `chunk_index`

### 7. Observability (LangSmith)
- **Tracing**: `@traceable` decorators on:
  - `_call_alarm_tool` (run_type=tool)
  - `_call_maint_tool` (run_type=tool)
  - `_gemini_generate` (run_type=llm) for `detect_intent` and `synthesize_answer`
- **LangGraph**: Auto-tracing state transitions and node execution
- **Metadata Captured**: Request ID, Trace ID, MCP server/tool, duration, outcome, API status code, retry count, retrieval query/scores, LLM latency/tokens, error details
- **Configuration**: `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT=maintenance-copilot`

### 8. External Services
- **Google Gemini API**: `gemini-2.5-flash` (LLM for intent, synthesis, RAG)
- **Hugging Face Hub**: `all-MiniLM-L6-v2` (embedding model)

## Request Flow: User Prompt → Grounded Answer

```
1. User submits query via Frontend (POST /chat)
2. Backend creates LangGraph initial state with session history
3. detect_intent (Gemini) → structured intent + routing flags
4. discover_mcp_tools → lists 13 alarm tools + 7 maintenance tools
5. plan_mcp_execution → emits query_plan (visible in UI)
6. Conditional parallel execution:
   a. execute_alarm_tools → Alarm MCP (streamable-HTTP) → Alarm API (HTTP+Bearer)
   b. execute_maintenance_tools → Maintenance MCP (streamable-HTTP) → CMMS API (HTTP)
   c. query_rag → RetrievalService → ChromaDB → Gemini (grounded) → citations
7. synthesize_answer (Gemini) → combines asset data + RAG context → final answer
8. Response: answer + citations + mcp_trace + query_plan + confidence
9. Frontend renders: chat message + side panels (citations, trace, plan)
10. LangSmith captures full trace with all spans
```

## Authentication Boundaries

| Boundary | Mechanism |
|----------|-----------|
| Frontend → Backend | CORS (no auth in demo) |
| Backend → MCP Clients | Internal (same network) |
| MCP Clients → MCP Servers | Streamable HTTP (MCP protocol) |
| Alarm MCP → Alarm API | Bearer token + trace headers |
| Maintenance MCP → CMMS API | No auth (internal demo) |
| Backend → Gemini API | API Key in env |
| Backend → LangSmith | API Key in env |

## Docker Compose Service Dependencies

```
alarm-api (8000)          → health check
    ↓ depends_on: healthy
alarm-mcp (9000)          → health check
    ↓ depends_on: healthy
maintenance-cmms (8001)   → health check
    ↓ depends_on: healthy
maintenance-mcp (9001)    → health check
    ↓ depends_on: healthy
rag-ingestion (batch)     → exits after indexing
    ↓
copilot-backend (8002)    → depends_on: alarm-mcp, maintenance-mcp
    ↓ depends_on
frontend (3000)           → depends_on: copilot-backend
```

## Key Architectural Decisions

1. **MCP Boundary Enforced**: Orchestrator never calls Alarm/CMMS APIs directly
2. **Two Independent MCP Servers**: Each runnable, testable, deployable separately
3. **Conditional Parallel Execution**: LangGraph routes based on intent flags
4. **RAG + MCP Unified**: Same workflow, both traced, both contribute to synthesis
5. **Streamable HTTP Transport**: Modern MCP transport, not stdio
6. **Per-Request MCP Sessions**: No persistent connections, stateless scaling
7. **Structured Metadata**: Every trace span includes server, tool, input, output, duration
8. **Prompt Injection Guard**: Detection on retrieved chunks before LLM