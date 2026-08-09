# API Integration Documentation

## Overview

This document describes the integration patterns between all API layers in the Maintenance Copilot system. The architecture enforces a strict boundary: the Copilot Backend **never calls source APIs directly**—all external data access goes through MCP servers.

---

## Integration Layers

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Frontend   │────▶│ Copilot Backend  │────▶│   MCP Clients   │────▶│   MCP Servers    │
│  (React)    │     │  (FastAPI)       │     │ (streamable-HTTP)│     │  (FastMCP)       │
└─────────────┘     └──────────────────┘     └─────────────────┘     └────────┬─────────┘
                                                                               │
                    ┌──────────────────────────────────────────────────────────┘
                    ▼
         ┌─────────────────────┐     ┌──────────────────┐
         │  Alarm API Simulator│     │  CMMS API        │
         │  (FastAPI :8000)    │     │  (FastAPI :8001) │
         └─────────────────────┘     └──────────────────┘
```

---

## Frontend → Copilot Backend

### Protocol
- **HTTP/JSON** over REST
- **Endpoint**: `POST http://localhost:8002/chat`
- **CORS**: Enabled for all origins (`*`)

### Request
```json
{
  "message": "What alarms occurred on BFP-101 in the last 30 days?",
  "session_id": "optional-uuid-for-multi-turn"
}
```

### Response
```json
{
  "session_id": "uuid",
  "answer": "For BFP-101... [1]",
  "citations": [
    {"citation_id": "[1]", "source": "boiler_feed_pump_101_manual.md", "asset_id": "BFP-101", "score": 0.89}
  ],
  "mcp_trace": [
    {"tool": "get_alarms", "server": "alarm-management", "input": {"asset_id": "BFP-101"}, "output": "42 alarms | top: High Discharge Pressure x12"}
  ],
  "query_plan": [
    "Intent: query_type=alarm_analysis, time_range=180d, alarms=yes, maintenance=SKIPPED, rag=yes",
    "Route: alarm tools → RAG → synthesis",
    "Asset scope: BFP-101 (named in query)",
    "Alarm tools complete: 1 alarm fetch(es), 1 summary(ies)",
    "RAG complete: 1 asset-specific + 1 general query, 3 citation(s)"
  ],
  "confidence": 0.85,
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

### Health Check
- `GET http://localhost:8002/health` → `{"status": "healthy", "service": "copilot-backend"}`

---

## Copilot Backend → MCP Clients (Streamable HTTP)

### Transport
- **Protocol**: MCP over Streamable HTTP (`streamablehttp_client`)
- **Connection**: Per-request (opened in `asynccontextmanager`, closed after use)
- **Initialization**: `session.initialize()` called on each connection

### Alarm MCP Client
- **URL**: `http://alarm-mcp:9000/mcp` (Docker) / `http://localhost:9000/mcp` (local)
- **Methods Used**:
  - `list_tools()` → tool discovery
  - `call_tool(name, args)` → tool invocation

### Maintenance MCP Client
- **URL**: `http://maintenance-mcp:9001/mcp` (Docker) / `http://localhost:9001/mcp` (local)
- **Methods Used**: Same as Alarm MCP

### Error Handling
```python
@traceable(run_type="tool", name="mcp_call_tool")
async def _call_alarm_tool(session, name, arguments):
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool error: {result.content[0].text}")
    return json.loads(result.content[0].text)
```

### Tracing
- `@traceable(run_type="tool", name="mcp_call_tool")` on both `_call_alarm_tool` and `_call_maint_tool`
- Captures: tool name, input args, output, duration, server name
- Correlated with LangGraph trace via Request ID

---

## MCP Servers → Source APIs (HTTP)

### Alarm MCP Server → Alarm API Simulator

**Base URL**: `http://alarm-api:8000` (Docker) / `http://localhost:8000` (local)

**Client Configuration**:
```python
client = httpx.AsyncClient(
    base_url=settings.alarm_api_base_url,
    headers={"Authorization": f"Bearer {settings.alarm_api_token}"},
    timeout=settings.request_timeout,  # 30s
)
```

**Authentication**: Bearer token (`demo-token`) on all requests
**Trace Headers**: Propagated (if present in incoming MCP request)

**Retry Logic** (`_request_with_retry`):
- Max 3 attempts
- Retries on: 5xx status, network errors
- Does NOT retry on: 4xx status (client errors)
- Raises last error after exhaustion

**Endpoint Mapping**:
| MCP Tool | Upstream Endpoint | Method |
|----------|-------------------|--------|
| `search_assets` | `/assets/search` | GET |
| `get_asset_metadata` | `/assets/{id}/metadata` | GET |
| `get_alarms` | `/alarms` | GET |
| `get_alarm_by_id` | `/alarms/{id}` | GET |
| `get_alarm_summary` | `/alarms/summary` | POST |
| `get_alarm_trends` | `/alarms/trends` | POST |
| `get_alarm_correlation` | `/alarms/correlation` | POST |
| `get_flood_analysis` | `/alarms/flood-analysis` | POST |
| `get_rationalization_candidates` | `/alarms/rationalization-candidates` | POST |
| `get_priority_score` | `/alarms/priority-score` | POST |
| `get_operator_recommendations` | `/recommendations/operator-actions` | POST |

**Health Check**: `GET /health` → proxies to upstream, returns `{"status": "ok", "upstream_alarm_api": "ok|unreachable"}`

---

### Maintenance MCP Server → CMMS API

**Base URL**: `http://maintenance-cmms:8001` (Docker) / `http://localhost:8001` (local)

**Client Configuration**:
```python
client = httpx.AsyncClient(
    base_url=settings.cmms_api_base_url,
    timeout=settings.request_timeout,  # 30s
)
```

**Authentication**: None (internal demo)
**Retry Logic**: Same as Alarm MCP (max 3, 5xx/network only)

**Endpoint Mapping**:
| MCP Tool | Upstream Endpoint | Method |
|----------|-------------------|--------|
| `search_assets` | `/assets` (client-side filter) | GET |
| `get_asset_metadata` | `/assets/{id}` | GET |
| `get_work_orders` | `/work-orders` | GET |
| `get_maintenance_logs` | `/maintenance-logs` | GET |
| `get_asset_work_order_summary` | `/assets/{id}/work-order-summary` | GET |
| `get_asset_maintenance_summary` | `/assets/{id}/maintenance-summary` | GET |
| `get_spare_parts` | `/spare-parts` | GET |

**Health Check**: `GET /health` → proxies to upstream, returns `{"status": "ok", "upstream_cmms": "ok|unreachable"}`

---

## Copilot Backend → RAG Retrieval Service

### Integration Pattern
- **Direct Python import** (not HTTP): `from rag.retrieval.retrieve import RetrievalService`
- **Instantiated once** at module load: `rag_client = RAGClient()`

### RAGClient Wrapper
```python
class RAGClient:
    def __init__(self):
        from rag.retrieval.retrieve import RetrievalService
        self.service = RetrievalService()

    def query(self, query: str, asset_id: Optional[str] = None) -> Dict:
        result = self.service.query(query, asset_id=asset_id)
        return {"answer": result.answer, "citations": result.citations, "confidence": result.confidence}
```

### RetrievalService Configuration (Env Vars)
| Variable | Default |
|----------|---------|
| `PERSIST_DIR` | `rag/chroma_db` |
| `COLLECTION_NAME` | `maintenance_docs` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `TOP_K` | `5` |
| `SCORE_THRESHOLD` | `0.3` |

### Tracing
- `query_rag` LangGraph node adds trace entry: `{"tool": "rag_query", "server": "rag", "input": {...}, "output": {...}}`
- RetrievalService methods not individually traced (internal)

---

## Copilot Backend → Gemini API (LLM)

### Client Configuration
```python
genai_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"
```

### Usage Points
1. **`detect_intent` node**: Structured intent extraction from user query
2. **`synthesize_answer` node**: Final answer generation from combined context
3. **`RetrievalService.generate_answer`**: RAG grounded generation

### Tracing
- `@traceable(run_type="llm", name="gemini_generate")` on `_gemini_generate()` helper
- Captures: prompt, response, token usage, latency
- Shared across all three usage points

---

## Observability Integration (LangSmith)

### Configuration (Env Vars)
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your-key>
LANGCHAIN_PROJECT=maintenance-copilot
```

### Automatic Tracing
- **LangGraph**: Auto-traces all node executions, state transitions
- **MCP Tools**: `@traceable(run_type="tool")` on `_call_alarm_tool`, `_call_maint_tool`
- **LLM Calls**: `@traceable(run_type="llm")` on `_gemini_generate`

### Metadata Enrichment
Each trace includes:
```python
# MCP tool traces
{"tool": "get_alarms", "server": "alarm-management", "input": {...}, "output": {...}, "timestamp": ...}

# LLM traces
{"run_type": "llm", "name": "gemini_generate", "inputs": {...}, "outputs": {...}}

# LangGraph node traces
{"node": "execute_alarm_tools", "state_keys": [...], "duration_ms": ...}
```

### Correlation IDs
- **Request ID**: Generated per `/chat` request (UUID)
- **Trace ID**: LangSmith trace ID (propagated through all spans)
- **Session ID**: User conversation session (for multi-turn)

---

## Docker Compose Networking

### Service Names (DNS)
| Service | Hostname | Port | Internal URL |
|---------|----------|------|--------------|
| alarm-api | `alarm-api` | 8000 | `http://alarm-api:8000` |
| alarm-mcp | `alarm-mcp` | 9000 | `http://alarm-mcp:9000/mcp` |
| maintenance-cmms | `maintenance-cmms` | 8001 | `http://maintenance-cmms:8001` |
| maintenance-mcp | `maintenance-mcp` | 9001 | `http://maintenance-mcp:9001/mcp` |
| copilot-backend | `copilot-backend` | 8002 | `http://copilot-backend:8002` |
| frontend | `frontend` | 3000 | `http://frontend:3000` |
| rag-ingestion | (batch) | - | - |

### Environment Variable Mapping (Docker)
```yaml
# docker-compose.yml
environment:
  - ALARM_MCP_URL=http://alarm-mcp:9000/mcp
  - MAINT_MCP_URL=http://maintenance-mcp:9001/mcp
  - ALARM_API_BASE_URL=http://alarm-api:8000
  - CMMS_API_BASE_URL=http://maintenance-cmms:8001
```

### Health Check Dependencies
```yaml
# docker-compose.yml
alarm-mcp:
  depends_on:
    alarm-api:
      condition: service_healthy

maintenance-mcp:
  depends_on:
    maintenance-cmms:
      condition: service_healthy

copilot-backend:
  depends_on:
    alarm-mcp:
      condition: service_healthy
    maintenance-mcp:
      condition: service_healthy

frontend:
  depends_on:
    copilot-backend:
      condition: service_healthy
```

---

## Local Development (Non-Docker)

### Override URLs
```bash
# .env or export
ALARM_MCP_URL=http://localhost:9000/mcp
MAINT_MCP_URL=http://localhost:9001/mcp
ALARM_API_BASE_URL=http://localhost:8000
CMMS_API_BASE_URL=http://localhost:8001
```

### Startup Order
1. Alarm API (`cd apps/alarm-api && python main.py`)
2. Maintenance CMMS (`cd connectors/maintenance && python main.py`)
3. Alarm MCP (`cd mcp-servers/alarm-management && python -m mcp_servers.alarm_management.server`)
4. Maintenance MCP (`cd mcp-servers/maintenance && python -m mcp_servers.maintenance.server`)
5. RAG Ingestion (`cd rag/ingestion && python ingest.py`)
6. Copilot Backend (`cd apps/backend && python main.py`)
7. Frontend (`cd apps/frontend && npm run dev`)

---

## Security Boundaries

| Boundary | Auth Mechanism | Notes |
|----------|----------------|-------|
| Frontend → Backend | None (CORS only) | Demo only; add JWT/OIDC for production |
| Backend → MCP Clients | Internal network | Docker network isolation |
| MCP Clients → MCP Servers | MCP protocol | Streamable HTTP, no auth in demo |
| Alarm MCP → Alarm API | Bearer token | `demo-token` in env; rotate for production |
| Maintenance MCP → CMMS | None | Internal demo; add mTLS for production |
| Backend → Gemini | API Key | In env, not logged |
| Backend → LangSmith | API Key | In env, not logged |

---

## Error Propagation

```
Upstream API (5xx)
    ↓
MCP Server retry (3x)
    ↓
MCP Tool Error (isError=true)
    ↓
MCP Client catches RuntimeError
    ↓
LangGraph node catches Exception
    ↓
mcp_trace entry with "error": "message"
    ↓
Conditional routing continues (other branches)
    ↓
synthesize_answer receives partial data
    ↓
Final answer notes limitation
    ↓
Frontend displays answer + error in trace tab
```

**Key Principle**: Partial failure → degraded response, not total failure. Other MCP servers and RAG continue.

---

## Versioning & Compatibility

| Interface | Versioning Strategy |
|-----------|---------------------|
| Frontend ↔ Backend | JSON schema (additive only) |
| Backend ↔ MCP Clients | MCP protocol (tool schemas) |
| MCP Servers ↔ Upstream APIs | OpenAPI spec (Postman for Alarm API) |
| RAG Service | Embedding model version pinned (`all-MiniLM-L6-v2`) |
| LLM Prompts | Versioned in code (prompt templates as constants) |

---

## Testing Integration Points

| Integration | Test Location | Coverage |
|-------------|---------------|----------|
| Frontend → Backend | Manual / E2E | Chat flow, citations, trace |
| Backend → MCP Clients | `tests/unit/mcp/` | Tool discovery, invocation, errors |
| MCP Servers → Upstream | `tests/unit/mcp/` | Retry, auth, error mapping |
| Backend → RAG | `tests/unit/` | Retrieval, citations, confidence |
| Full E2E | `tests/e2e/test_mcp_rag_workflow.py` | MCP + RAG combined |
| Dual MCP Client | `tests/integration/test_dual_mcp_client.py` | Both servers concurrently |

---

## Performance Characteristics

| Hop | Typical Latency | Notes |
|-----|-----------------|-------|
| Frontend → Backend | 10-50ms | LAN |
| Backend → MCP Client (connect) | 20-100ms | Streamable HTTP handshake |
| MCP Client → MCP Server | 5-20ms | Same network |
| MCP Server → Upstream API | 50-200ms | Depends on query complexity |
| Backend → RAG (embed) | 50-150ms | SentenceTransformer CPU |
| Backend → RAG (ChromaDB) | 10-50ms | Local file DB |
| Backend → Gemini API | 1-3s | External API |
| **Total (happy path)** | **3-5s** | Parallel MCP + RAG |
| **Total (with retries)** | **5-10s** | Degraded |

---

## Monitoring Endpoints

| Service | Health | Metrics |
|---------|--------|---------|
| Frontend | `GET /` | - |
| Copilot Backend | `GET /health` | - |
| Alarm MCP | `GET /health` | Upstream status |
| Maintenance MCP | `GET /health` | Upstream status |
| Alarm API | `GET /health` | - |
| CMMS API | `GET /health` | - |
| LangSmith | Dashboard | Traces, latency, errors |