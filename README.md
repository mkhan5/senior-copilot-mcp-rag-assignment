# Maintenance and Work Order Intelligence System

A comprehensive maintenance copilot system that integrates alarm management, maintenance history, and document knowledge using MCP (Model Context Protocol), RAG (Retrieval-Augmented Generation), and LLM-based synthesis.

## Demo Videos
The videos demonstrating the solution are available in the assets folder. Two videos have been uploaded.

The first video demonstrates various queries, most of which are taken from the `Submission_and_Evaluation_Guidelines.md` file.

The second video demonstrates queries in different forms, shows the running system using a Docker build, and provides an explanation of the architecture.

Links: 
1. [assets/copilot_demo1.mp4](assets/copilot_demo1.mp4)
2. [assets/copilot_demo2_with_architecture.mp4](assets/copilot_demo2_with_architecture.mp4)

## Selected Use Case

**Industrial Maintenance Copilot for Alarm Analysis and Work Order Intelligence**

This system enables maintenance engineers and operators to investigate alarms, correlate them with maintenance history, and retrieve relevant procedural knowledge from equipment manuals—all through a natural language chat interface. The copilot orchestrates across two independent MCP servers (Alarm Management and Maintenance CMMS) and a RAG pipeline to provide grounded, citation-backed answers.

## Main Capabilities

- **2 MCP Servers integration**: Two MCP servers were integrated in the workflow - one for Alarm Management and one Maintenance CMMS.
- **End to end workflow**: End to end workflow ensures Alarm API and CMMS database are accessed via 2 MCP servers only, along with the Document RAG in a combined single workflow. 
- **Citation, Plan & Tracing**: The frontend and backend clearly shows the document citation, Agent Plan and Tracing.
- **GEMINI LLM**: Google Gemini-2.5-Flash model leveraged as the LLM.
- **Document Knowledge (RAG)**: Grounded answers from equipment manuals, procedures, checklists with citations
- **Multi-turn Conversation**: Session-aware context retention for follow-up questions
- **Full Observability**: LangSmith tracing across MCP tools, LLM calls, and LangGraph nodes
- **Alarm Analysis**: Query, filter, and summarize alarms across assets with KPIs (recurring rate, ack delay)
- **Alarm Correlation**: Co-occurrence analysis between assets with configurable lag windows
- **Operator Recommendations**: Get actionable recommendations for specific alarms with asset context
- **Maintenance History**: Query work orders, maintenance logs, and asset summaries from CMMS
- **Spare Parts Lookup**: Retrieve critical spare parts inventory for assets



## Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **Backend Orchestration** | FastAPI, LangGraph (StateGraph), Pydantic |
| **MCP Servers** | 2 FastMCP servers -  Alarm Management MCP Server & Maintenance CMMS MCP Server (`Streamable HTTP transport`) |
| **MCP Clients** | 2 MCP Python SDK clients (`streamablehttp_client`) |
| **Source APIs** | FastAPI (Alarm Simulator), FastAPI + SQLite (CMMS) |
| **RAG Ingestion** | ChromaDB PersistentClient, SentenceTransformers (`all-MiniLM-L6-v2`), LangChain Text Splitters |
| **RAG Retrieval** | ChromaDB vector search + metadata filters, Google Gemini 2.5 Flash |
| **LLM** | Google Gemini 2.5 Flash (via GenAI SDK) |
| **Embeddings** | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| **Vector Database** | ChromaDB (cosine similarity, HNSW index) |
| **Observability** | LangSmith (`@traceable`, auto LangGraph tracing) |
| **Packaging** | Docker, Docker Compose |
| **Testing** | pytest (unit, integration, e2e) |

## MCP Server Description

### 1. Alarm Management MCP Server (`alarm-management-mcp`)

**Purpose**: Exposes the Alarm Management API as MCP tools for alarm querying, analysis, and correlation.

**Transport**: Streamable HTTP on port 9000 (`/mcp` endpoint)

**Upstream**: Alarm API Simulator at `http://alarm-api:8000` (FastAPI, Postman spec compliant)

**Authentication**: Bearer token (`demo-token`) propagated to upstream

**Resilience**: Retry (max 3) on 5xx/network errors, 30s timeout

**Health Check**: `GET /health` → proxies to upstream Alarm API

**Tools (13)**: `search_assets`, `get_asset_metadata`, `get_alarms`, `get_alarm_by_id`, `get_alarm_summary`, `get_alarm_trends`, `get_alarm_correlation`, `get_flood_analysis`, `get_rationalization_candidates`, `get_priority_score`, `get_operator_recommendations`

**Run Independently**:
```bash
cd mcp-servers/alarm-management
pip install -r requirements.txt
export ALARM_API_BASE_URL=http://localhost:8000
export ALARM_API_TOKEN=demo-token
python -m mcp_servers.alarm_management.server
# Server runs on http://localhost:9000/mcp
curl http://localhost:9000/health
```

### 2. Maintenance CMMS MCP Server (`maintenance-cmms-mcp`)

**Purpose**: Exposes the CMMS (Computerized Maintenance Management System) API as MCP tools for work orders, maintenance logs, and asset summaries.

**Transport**: Streamable HTTP on port 9001 (`/mcp` endpoint)

**Upstream**: CMMS API at `http://maintenance-cmms:8001` (FastAPI + SQLite)

**Authentication**: None (internal demo)

**Resilience**: Retry (max 3) on 5xx/network errors, 30s timeout

**Health Check**: `GET /health` → proxies to upstream CMMS API

**Tools (7)**: `search_assets`, `get_asset_metadata`, `get_work_orders`, `get_maintenance_logs`, `get_asset_work_order_summary`, `get_asset_maintenance_summary`, `get_spare_parts`

**Run Independently**:
```bash
cd mcp-servers/maintenance
pip install -r requirements.txt
export CMMS_API_BASE_URL=http://localhost:8001
python -m mcp_servers.maintenance.server
# Server runs on http://localhost:9001/mcp
curl http://localhost:9001/health
```

## MCP Tool List

See [docs/mcp-tool-catalog.md](docs/mcp-tool-catalog.md) for complete tool specifications including input/output schemas, authentication, error behavior, timeouts, and example invocations.

### Alarm Management Tools (13)
1. `search_assets` — Search assets by name/ID
2. `get_asset_metadata` — Detailed asset information
3. `get_alarms` — Filtered, paginated alarm list
4. `get_alarm_by_id` — Single alarm details
5. `get_alarm_summary` — KPIs grouped by field (alarm_count, recurring_rate, avg_ack_delay)
6. `get_alarm_trends` — Time-bucketed trends (daily/hourly)
7. `get_alarm_correlation` — Co-occurrence analysis between assets
8. `get_flood_analysis` — Alarm flood detection in units
9. `get_rationalization_candidates` — Recurring/stale alarm identification
10. `get_priority_score` — Alarm priority calculation
11. `get_operator_recommendations` — Actionable operator guidance

### Maintenance CMMS Tools (7)
12. `search_assets` — Search CMMS assets
13. `get_asset_metadata` — CMMS asset details
14. `get_work_orders` — Filtered work order list
15. `get_maintenance_logs` — Maintenance activity logs
16. `get_asset_work_order_summary` — Work order KPIs (total, open, completed, cost)
17. `get_asset_maintenance_summary` — Maintenance activity KPIs (activities, hours, cost)
18. `get_spare_parts` — Spare parts inventory

## RAG Corpus and Ingestion Approach

### Corpus
5 markdown documents in `rag/documents/`:
- `boiler_feed_pump_101_manual.md` — Equipment manual for BFP-101/102
- `compressor_201_manual.md` — Equipment manual for COMP-201/202
- `motor_maintenance_procedure.md` — Maintenance procedures for motors
- `pump_inspection_checklist.md` — Inspection checklists for pumps
- `spare_parts_guidance.md` — Spare parts criticality guidance


### Ingestion Pipeline
```
Documents → Loader (md/txt/pdf) → RecursiveCharacterTextSplitter
  → SentenceTransformer (all-MiniLM-L6-v2) → ChromaDB PersistentClient
  → Collection: maintenance_docs (cosine similarity)
```

### Metadata Enrichment
Auto-extracted per chunk: `asset_id`, `asset_name`, `doc_type` (equipment_manual, maintenance_procedure, inspection_checklist, spare_parts_guidance), `source`, `chunk_index`, `chunk_count`

### Retrieval
- Vector search + metadata filters (`asset_id`, `doc_type`)
- Score threshold: 0.3 (cosine similarity)
- Top-k: 5 (configurable)
- Prompt injection detection (12 patterns, logged)
- Grounded generation with Gemini 2.5 Flash + citation IDs

### Run Ingestion
```bash
# Via Docker Compose (recommended)
docker-compose run --rm rag-ingestion

# Or locally
cd rag/ingestion
pip install -r requirements.txt
python ingest.py
```

## Quick-Start Instructions

### Prerequisites
- Docker & Docker Compose (v2+)
- Google Gemini API Key (get from [https://aistudio.google.com/](https://aistudio.google.com/))
- Optional: LangSmith API Key for tracing (get from [https://smith.langchain.com/](https://smith.langchain.com/))

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
# Optional: add LANGCHAIN_API_KEY for tracing
```

### 2. Build and Start All Services
```bash
docker-compose up --build -d
```

This starts 7 services with health checks and dependency ordering:
1. `alarm-api` (port 8000) — Alarm simulator
2. `maintenance-cmms` (port 8001) — CMMS API
3. `alarm-mcp` (port 9000) — Alarm MCP server
4. `maintenance-mcp` (port 9001) — Maintenance MCP server
5. `rag-ingestion` (batch) — Document indexing (exits after completion)
6. `copilot-backend` (port 8002) — LangGraph orchestration
7. `frontend` (port 3000) — React chat UI

### 3. Ingest Documents (one-time, after first startup)
```bash
docker-compose run --rm rag-ingestion
```

### 4. Access Applications
- **Frontend (Chat UI)**: http://localhost:3000
- **Copilot Backend API**: http://localhost:8002
- **Alarm API**: http://localhost:8000
- **Maintenance CMMS API**: http://localhost:8001
- **Alarm MCP**: http://localhost:9000/mcp
- **Maintenance MCP**: http://localhost:9001/mcp

### 5. Verify Health
```bash
curl http://localhost:8000/health   # Alarm API
curl http://localhost:8001/health   # CMMS API
curl http://localhost:9000/health   # Alarm MCP
curl http://localhost:9001/health   # Maintenance MCP
curl http://localhost:8002/health   # Copilot Backend
```

## Configuration

### Environment Variables (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | **Required** Google Gemini API key | - |
| `LANGCHAIN_API_KEY` | LangSmith tracing API key | - |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing | `true` |
| `LANGCHAIN_PROJECT` | LangSmith project name | `maintenance-copilot` |
| `ALARM_API_BASE_URL` | Alarm API base URL | `http://alarm-api:8000` |
| `ALARM_API_TOKEN` | Alarm API Bearer token | `demo-token` |
| `CMMS_API_BASE_URL` | CMMS API base URL | `http://maintenance-cmms:8001` |
| `ALARM_MCP_URL` | Alarm MCP URL (backend client) | `http://alarm-mcp:9000/mcp` |
| `MAINT_MCP_URL` | Maintenance MCP URL (backend client) | `http://maintenance-mcp:9001/mcp` |
| `DOCUMENTS_DIR` | RAG source documents directory | `rag/documents` |
| `PERSIST_DIR` | ChromaDB persistence directory | `rag/chroma_db` |
| `COLLECTION_NAME` | ChromaDB collection name | `maintenance_docs` |
| `EMBEDDING_MODEL` | SentenceTransformer model | `all-MiniLM-L6-v2` |
| `CHUNK_SIZE` | RAG chunk size | `500` |
| `CHUNK_OVERLAP` | RAG chunk overlap | `50` |
| `TOP_K` | Retrieval top-k | `5` |
| `SCORE_THRESHOLD` | Retrieval score threshold | `0.3` |

See `.env.example` for complete list.

## Build and Run Commands

### Docker Compose (Recommended)
```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f copilot-backend

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Local Development (Non-Docker)
```bash
# Terminal 1: Alarm API
cd apps/alarm-api && pip install -r requirements.txt && python main.py

# Terminal 2: Maintenance CMMS
cd connectors/maintenance && pip install -r requirements.txt && python main.py

# Terminal 3: Alarm MCP
cd mcp-servers/alarm-management && pip install -r requirements.txt && python -m mcp_servers.alarm_management.server

# Terminal 4: Maintenance MCP
cd mcp-servers/maintenance && pip install -r requirements.txt && python -m mcp_servers.maintenance.server

# Terminal 5: RAG Ingestion (once)
cd rag/ingestion && pip install -r requirements.txt && python ingest.py

# Terminal 6: Copilot Backend
cd apps/backend && pip install -r requirements.txt && python main.py

# Terminal 7: Frontend
cd apps/frontend && npm install && npm run dev
```

## Test Commands

```bash
# Unit tests (MCP tools)
cd tests/unit/mcp && python -m pytest test_maintenance_tools.py -v

# Integration tests (dual MCP client)
cd tests/integration && python -m pytest test_dual_mcp_client.py -v

# E2E tests (MCP + RAG workflow)
cd tests/e2e && python -m pytest test_mcp_rag_workflow.py -v

# RAG ingestion test
cd rag/ingestion && python ingest.py

# RAG retrieval test
cd rag/retrieval && python retrieve.py

# Frontend build test
cd apps/frontend && npm run build

# Backend tests
cd apps/backend && python -m pytest tests/ -v
```

## Sample Interactions

### Alarm Analysis
> **User**: "What alarms occurred on Boiler Feed Pump 101 in the last 30 days?"
> **Copilot**: Retrieves alarms via `get_alarms` + `get_alarm_summary` from Alarm MCP, shows recurring high discharge pressure alarms with KPIs, cites alarm response procedure from BFP-101 manual [1].

### Maintenance History
> **User**: "Show me maintenance history for Compressor 201"
> **Copilot**: Queries Maintenance MCP for work orders, maintenance logs, and summaries. Returns 24 work orders (22 completed), 45 maintenance activities, total cost $45,750. Cites compressor manual for context [2].

### Combined Analysis
> **User**: "Compare alarm patterns between BFP-101 and COMP-201 and explain likely causes"
> **Copilot**: 
> 1. Calls `get_alarm_correlation` on Alarm MCP for co-occurrence
> 2. Queries Maintenance MCP for both assets' work order history
> 3. Queries RAG for pump and compressor troubleshooting guides
> 4. Synthesizes: BFP-101 shows recurring high pressure (12x, recurring_rate=0.85); COMP-201 shows vibration alarms. Maintenance logs reveal recent seal replacement on BFP-101. RAG cites bearing wear as common cause [3,4].

### Procedure Lookup
> **User**: "What is the surge alarm response procedure for compressors?"
> **Copilot**: Queries RAG with `doc_type=equipment_manual` filter. Returns surge control procedure from compressor manual with immediate actions and escalation steps [5].

### Spare Parts
> **User**: "What are the critical spare parts for pumps?"
> **Copilot**: Calls `get_spare_parts` on Maintenance MCP (filter asset_type=pump via search). Returns critical spares: mechanical seals, bearings, impellers. RAG cites spare parts guidance for criticality classification [6].

## Architecture Summary

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend   │────▶│ Copilot Backend  │────▶│  MCP Clients    │
│  (React)    │     │  (LangGraph)     │     │ (streamable-HTTP)│
└─────────────┘     └────────┬─────────┘     └────────┬────────┘
                             │                        │
                    ┌────────┴────────┐       ┌────────┴────────┐
                    ▼                 ▼       ▼                 ▼
             ┌────────────┐    ┌────────────┐ ┌──────────┐ ┌──────────┐
             │   RAG      │    │Alarm MCP   │ │Maint MCP │ │ ChromaDB │
             │ Retrieval  │    │ (9000)     │ │ (9001)   │ │          │
             └─────┬──────┘    └─────┬──────┘ └────┬─────┘ └──────────┘
                   │                 │             │
                   ▼                 ▼             ▼
            ┌────────────┐    ┌────────────┐ ┌────────────┐
            │  Gemini    │    │ Alarm API  │ │  CMMS API  │
            │  2.5 Flash │    │  (8000)    │ │  (8001)    │
            └────────────┘    └────────────┘ └────────────┘
```

**Request Flow**:
1. User query → Frontend → Backend `/chat`
2. `detect_intent` (Gemini) → structured intent + routing flags
3. `discover_mcp_tools` → lists 13+7 tools from both MCP servers
4. `plan_mcp_execution` → emits query plan (visible in UI)
5. Conditional parallel execution:
   - `execute_alarm_tools` → Alarm MCP → Alarm API
   - `execute_maintenance_tools` → Maintenance MCP → CMMS API
   - `query_rag` → ChromaDB → Gemini (grounded) → citations
6. `synthesize_answer` (Gemini) → combines all sources → final answer
7. Response: answer + citations + mcp_trace + query_plan + confidence
8. LangSmith captures full trace with all spans

**Key Architectural Principles**:
- MCP boundary enforced: Backend never calls Alarm/CMMS APIs directly
- Two independent MCP servers (independently runnable, testable)
- Streamable HTTP transport (production-ready, not stdio)
- Per-request MCP sessions (stateless, horizontally scalable)
- Intent-driven conditional routing (avoids unnecessary calls)
- RAG as first-class workflow node (same trace as MCP)
- Full observability via LangSmith

## Assumptions

1. **Demo Environment**: Single-tenant, no authentication on frontend/backend, demo Bearer token for Alarm API
2. **Asset Registry**: Alarm API is the source of truth for assets; Maintenance CMMS mirrors subset
3. **Document Corpus**: 5 markdown files represent maintenance knowledge base; no PDF/Word in demo
4. **LLM Availability**: Gemini 2.5 Flash API accessible; no fallback model configured
5. **Network**: All services on same Docker network; DNS resolution via service names
6. **Data Volumes**: Small demo datasets (<1000 alarms, <500 work orders, <135 RAG chunks)
7. **Concurrency**: Single backend instance; in-memory session store sufficient
8. **Observability**: LangSmith SaaS used; no local tracing alternative in demo
9. **Ingestion**: Batch job run manually/once; no incremental updates
10. **Time Zones**: All timestamps UTC (ISO 8601 with Z suffix)

## Known Limitations

**Key Limitations (Accepted for Demo)**:
- Simple Bearer token (`demo-token`) for Alarm API
- SQLite CMMS with synthetic demo data
- ChromaDB PersistentClient (embedded, not scalable)
- Basic prompt injection detection (logging only)
- No CI/CD pipeline (tests run manually)

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Complete architecture with layers, request flow, auth boundaries |
| [docs/mcp-tool-catalog.md](docs/mcp-tool-catalog.md) | All 20 MCP tools with schemas, examples, error behavior |
| [docs/rag-design.md](docs/rag-design.md) | RAG pipeline: ingestion, chunking, retrieval, generation, citations |
| [docs/api-integration.md](docs/api-integration.md) | Integration patterns between all API layers |
| [docs/design-decisions.md](docs/design-decisions.md) | 25 key decisions with rationale and trade-offs |

## Architecture Diagrams

- `docs/architecture_diagram_high-level.png` — High-level system overview
- `docs/architecture_diagram_detailed.png` — Detailed component diagram
- `docs/architecture_high-level.mmd` — Mermaid source for high-level
- `docs/architecture_detailed.mmd` — Mermaid source for detailed

## Demo Evidence

- **Demo Video**: See `assets/` folder
- **MCP Tool Discovery View**: Frontend side panel "Query Plan" tab
- **MCP Execution Trace**: Frontend side panel "MCP Trace" tab
- **RAG Citations**: Frontend side panel "Citations" tab + inline `[1]`, `[2]` in answers
- **Successful Scenario**: Alarm analysis + maintenance history + RAG citation
- **Degraded Scenario**: MCP server failure → partial answer with error in trace

## Repository Sharing Checklist

- [x] Repository accessible
- [x] MCP servers run independently (`python -m mcp_servers.alarm_management.server`)
- [x] Copilot connects through MCP (never direct API calls)
- [x] Sample documents present in `rag/documents/`
- [x] RAG ingestion succeeds (`docker-compose run --rm rag-ingestion`)
- [x] Citations visible in UI and API response
- [x] Combined MCP+RAG scenario works (e.g., "Compare BFP-101 and COMP-201")
- [x] Setup works from clean environment (`docker-compose up --build`)
- [x] No secrets committed (`.env.example` provided, `.env` in `.gitignore`)
- [x] Tests pass (unit, integration, e2e)
- [x] Architecture diagrams included (`docs/*.png`, `docs/*.mmd`)
- [ ] GitHub Actions CI status visible (to be added)
- [ ] Evaluator access granted (private repo)
- [ ] Demo video uploaded and linked (to be added)

## Submission Message Template

```
Subject: Senior Software Engineer Copilot Assignment Submission

Repository:
<GitHub repository URL>

Selected use case:
Industrial Maintenance Copilot for Alarm Analysis and Work Order Intelligence

MCP server:
Alarm Management MCP (13 tools) + Maintenance CMMS MCP (7 tools)
Start: docker-compose up --build (or independently via python -m mcp_servers.{alarm_management,maintenance}.server)

Document RAG:
Corpus: 5 markdown maintenance documents (manuals, procedures, checklists)
Ingestion: docker-compose run --rm rag-ingestion
Retrieval: ChromaDB vector search + metadata filters → Gemini 2.5 Flash grounded generation with citations

Run instructions:
docker-compose up --build -d
docker-compose run --rm rag-ingestion
Open http://localhost:3000

Test instructions:
pytest tests/ -v

Demo:
assets/ folder (screenshots)
Demo video: [link to be added]

Known limitations:
See docs/known-limitations.md (in-memory sessions, no auth, demo token, batch ingestion, etc.)

Estimated implementation time:
~24 hours
```
