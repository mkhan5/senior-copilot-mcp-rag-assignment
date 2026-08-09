# Design Decisions

This document records key architectural and implementation decisions, their rationale, and trade-offs.

---

## 1. MCP as Mandatory Integration Layer

**Decision**: All external data access (Alarm API, CMMS API) must go through MCP servers. The Copilot Backend never calls source APIs directly.

**Rationale**:
- Enforces separation of concerns: orchestration vs. integration
- MCP servers are independently testable, deployable, replaceable
- Demonstrates MCP protocol proficiency (requirement)
- Enables tool discovery, schema validation, tracing at protocol level
- Allows swapping upstream implementations without changing orchestrator

**Trade-offs**:
- Additional network hop (Backend → MCP → API)
- More moving parts to operate
- Slightly higher latency vs. direct calls

---

## 2. Two Independent MCP Servers (Not One Monolith)

**Decision**: Separate `alarm-management-mcp` and `maintenance-cmms-mcp` servers, each with own FastMCP instance, port, and tool set.

**Rationale**:
- Different domains: alarms vs. maintenance/CMMS
- Different upstream APIs with different auth (Bearer vs. none)
- Different scaling/availability requirements
- Clear ownership boundaries
- Each runnable independently for testing

**Trade-offs**:
- Backend must manage two MCP connections
- Tool discovery runs twice (parallelized)
- Slightly more operational complexity

---

## 3. Streamable HTTP Transport (Not stdio)

**Decision**: Use MCP Streamable HTTP transport (`streamablehttp_client`) instead of stdio subprocesses.

**Rationale**:
- Production-ready: stateless, horizontally scalable
- Works naturally in containerized environments (Docker/K8s)
- Supports connection pooling, load balancing
- Health checks via HTTP `/health` endpoint
- Better observability (standard HTTP metrics)
- stdio is for local development / CLI tools only

**Trade-offs**:
- Requires network connectivity (vs. local process)
- Additional HTTP overhead per call
- Need service discovery / DNS in Docker

---

## 4. Per-Request MCP Sessions (Not Persistent)

**Decision**: Open MCP connection per request (in `asynccontextmanager`), close after use. No persistent sessions.

**Rationale**:
- Stateless: enables horizontal scaling of backend
- No session affinity needed
- Simpler failure recovery (no stale connections)
- Matches serverless / cloud-run patterns
- MCP `initialize()` is fast (~10-50ms)

**Trade-offs**:
- `initialize()` handshake on every request
- Slightly higher latency vs. persistent connection
- Cannot use MCP notifications/subscriptions (not needed)

---

## 5. LangGraph for Orchestration (Not Custom State Machine)

**Decision**: Use LangGraph (StateGraph) for the 7-node workflow with conditional edges.

**Rationale**:
- Built-in state management with reducers (`Annotated`)
- Native conditional routing (`add_conditional_edges`)
- First-class async support (`ainvoke`)
- LangSmith auto-tracing of all nodes/edges
- Checkpointing for resilience (future)
- Visual debugging (LangGraph Studio)

**Trade-offs**:
- Learning curve (TypedDict, reducers, conditional edges)
- Framework dependency
- Overkill for simple linear flows (but ours is conditional/parallel)

---

## 6. Intent-Driven Conditional Routing

**Decision**: Use LLM (`detect_intent` node) to extract structured intent with boolean flags (`needs_alarms`, `needs_maintenance`, `needs_documents`, `needs_correlation`), then conditionally execute nodes.

**Rationale**:
- Avoids unnecessary MCP/RAG calls (cost, latency)
- Handles diverse query types: alarm-only, maintenance-only, combined, procedure lookup
- Explicit `query_plan` emitted for UI visibility
- Graceful degradation: if one MCP fails, others continue

**Trade-offs**:
- LLM call adds ~1-2s latency
- Intent extraction can be wrong (mitigated: defaults to all true)
- More complex than fixed pipeline

---

## 7. Asset Resolution via MCP (Not Hardcoded)

**Decision**: Resolve asset IDs at runtime by calling `search_assets` on Alarm MCP, not using hardcoded lists.

**Rationale**:
- Single source of truth: Alarm API owns asset registry
- Supports new assets without code changes
- Works for category queries ("all high-criticality pumps")
- Handles fuzzy matching ("boiler pump" → BFP-101, BFP-102)

**Trade-offs**:
- Extra MCP call per query
- Depends on Alarm MCP availability
- Slightly slower than in-memory lookup

---

## 8. RAG as First-Class Workflow Node

**Decision**: `query_rag` is a LangGraph node on equal footing with MCP tool nodes, not a post-processing step.

**Rationale**:
- MCP and RAG participate in same trace
- Conditional execution based on intent (`needs_documents`)
- Citations flow through state to synthesis node
- Unified error handling and tracing

**Trade-offs**:
- RAG latency adds to critical path (parallelized with MCP)
- More complex state management

---

## 9. ChromaDB PersistentClient (Not Server Mode)

**Decision**: Use `chromadb.PersistentClient` (embedded, file-based) instead of ChromaDB server.

**Rationale**:
- Zero infrastructure: no separate container/service
- Simpler Docker Compose (one less service)
- Sufficient for demo-scale corpus (~135 chunks)
- Fast local I/O (no network hop)
- Easy backup (copy directory)

**Trade-offs**:
- Single-writer limitation (ingestion vs. concurrent reads)
- Not horizontally scalable
- No remote access (by design)

---

## 10. all-MiniLM-L6-v2 Embedding Model

**Decision**: Use `sentence-transformers/all-MiniLM-L6-v2` (384-dim, 22M params) for embeddings.

**Rationale**:
- Runs on CPU (no GPU required)
- Fast inference (~50ms per batch)
- Good semantic quality for technical text
- Small model size (~90MB)
- Deterministic (fixed weights)

**Trade-offs**:
- Less accurate than larger models (e.g., BGE, E5)
- English-only (adequate for this corpus)
- Fixed vocabulary

---

## 11. Gemini 2.5 Flash for All LLM Tasks

**Decision**: Single model (`gemini-2.5-flash`) for intent extraction, RAG generation, and answer synthesis.

**Rationale**:
- Cost-effective (Flash tier)
- Strong reasoning for structured output (JSON)
- Good at following citation instructions
- Single API key / quota management
- Low latency (~1-3s)

**Trade-offs**:
- Not specialized per task (e.g., smaller model for intent)
- Single point of failure (API quota, latency)
- Vendor lock-in (Google)

---

## 12. Citation Format: Inline [1], [2] + Structured JSON

**Decision**: LLM emits inline citation markers (`[1]`, `[2]`), backend returns structured citation array.

**Rationale**:
- Human-readable in chat answer
- Machine-processable for UI side panel
- Matches academic citation convention
- Enables click-through to source in UI

**Trade-offs**:
- Requires prompt discipline (enforced in RAG prompt)
- LLM may hallucinate citation numbers (mitigated: only real IDs provided)

---

## 13. In-Memory Session Store (Not Redis/DB)

**Decision**: Python dict `_session_store` for multi-turn conversation history.

**Rationale**:
- Zero infrastructure for demo
- Sufficient for single-instance backend
- Last 20 turns per session (bounded memory)
- Simple implementation

**Trade-offs**:
- Lost on backend restart
- Not shared across backend replicas
- No persistence for audit

---

## 14. LangSmith for Observability (Not Custom Logging)

**Decision**: Use LangSmith (`@traceable`, auto LangGraph tracing) for all observability.

**Rationale**:
- Purpose-built for LLM/MCP/agent tracing
- Captures inputs, outputs, latency, tokens automatically
- Correlates across MCP tools, LLM calls, graph nodes
- Dashboard for debugging and evaluation
- Standard in LangChain ecosystem

**Trade-offs**:
- External SaaS dependency (API key required)
- Cost at scale
- Data leaves infrastructure

---

## 15. Docker Compose for Local Packaging

**Decision**: Single `docker-compose.yml` starts all 7 services with health checks and dependencies.

**Rationale**:
- One-command startup: `docker compose up --build`
- Service dependencies via `depends_on: condition: service_healthy`
- Mirrors production topology (separate containers)
- Easy for evaluators to run

**Trade-offs**:
- Not production-grade (no rolling updates, secrets mgmt)
- Resource intensive (7 containers)
- Local file mounts for ChromaDB persistence

---

## 16. Pydantic Models for MCP Tool Schemas

**Decision**: Define all MCP tool arguments as Pydantic `BaseModel` classes with `Field` descriptions.

**Rationale**:
- Automatic JSON schema generation for MCP tool registration
- Input validation at MCP server boundary
- Self-documenting (descriptions → tool metadata)
- Type safety in Python code

**Trade-offs**:
- Boilerplate for each tool
- Schema changes require server restart

---

## 17. Retry Only on 5xx/Network Errors (Not 4xx)

**Decision**: MCP servers retry upstream calls only on 5xx status codes and network errors, never on 4xx.

**Rationale**:
- 4xx = client error (bad request, not found) → retry won't help
- 5xx = server error → transient, worth retrying
- Network errors → transient
- Prevents infinite loops on validation errors

**Trade-offs**:
- Upstream 4xx propagates immediately to user
- No automatic recovery from bad requests

---

## 18. Prompt Injection Detection (Logging Only)

**Decision**: Detect prompt injection patterns in retrieved chunks, log warning, continue processing.

**Rationale**:
- Defense-in-depth: catches obvious attacks
- Non-blocking: doesn't break legitimate queries with similar phrases
- Observable: appears in logs/LangSmith for review
- Simpler than sanitization/rewriting

**Trade-offs**:
- Doesn't prevent sophisticated attacks
- False positives possible (logged only)

---

## 19. Score Threshold 0.3 for Retrieval

**Decision**: Only return chunks with cosine similarity score ≥ 0.3 (distance ≤ 0.7).

**Rationale**:
- Filters out noise (random semantic matches)
- Balances recall vs. precision for technical corpus
- Tuned empirically on sample queries
- Configurable via `SCORE_THRESHOLD` env var

**Trade-offs**:
- May miss relevant chunks with lower scores
- Threshold is heuristic, not calibrated

---

## 20. Confidence = min(avg_score * 1.2, 1.0)

**Decision**: RAG confidence derived from average retrieval score, scaled by 1.2x, capped at 1.0.

**Rationale**:
- Rewards high-quality retrieval
- Penalizes low-score results
- Simple, interpretable formula
- Used in synthesis for weighting

**Trade-offs**:
- Not statistically calibrated
- Doesn't account for answer correctness
- Heuristic multiplier (1.2)

---

## 21. No Authentication on Frontend/Backend (Demo)

**Decision**: CORS `*` only, no JWT/OIDC/API keys on `/chat` endpoint.

**Rationale**:
- Simplifies evaluation (no token management)
- Focus on MCP/RAG architecture, not auth
- Internal network in Docker

**Trade-offs**:
- Not production-ready
- Anyone with network access can query
- No rate limiting

---

## 22. Bearer Token for Alarm API Only

**Decision**: Alarm API requires Bearer token (`demo-token`); CMMS API has no auth.

**Rationale**:
- Demonstrates auth propagation through MCP
- Alarm API spec (Postman) mandates it
- CMMS is internal demo service

**Trade-offs**:
- Inconsistent auth model
- Token hardcoded in env (not secret manager)

---

## 23. Synchronous RAG Ingestion (Batch Job)

**Decision**: `rag-ingestion` runs as Docker Compose one-shot service, exits after indexing.

**Rationale**:
- Simple: run once at startup or manually
- No scheduler needed
- Idempotent (ChromaDB `get_or_create_collection`)

**Trade-offs**:
- No incremental updates
- Must re-run if documents change
- Blocks startup if large corpus

---

## 24. Markdown Documents as Source (Not PDF/Word)

**Decision**: Corpus is 5 `.md` files in `rag/documents/`.

**Rationale**:
- Version-controlled in Git (diffable)
- Easy to author/edit/review
- No binary parsing issues
- Rich structure (headings) for chunking

**Trade-offs**:
- Limited to text-based content
- No tables/images extraction
- Manual conversion from original formats

---

## 25. Single Collection in ChromaDB

**Decision**: All documents in one collection `maintenance_docs` with metadata filters.

**Rationale**:
- Simpler query API (single `collection.query()`)
- Metadata filters (`asset_id`, `doc_type`) enable scoping
- Small corpus doesn't need sharding

**Trade-offs**:
- No per-document access control
- All vectors in one HNSW index (fine for <10k chunks)
- Cross-document contamination possible (mitigated: filters)

---

## Decision Log Format

For future decisions, use:
```
## N. Short Title

**Decision**: What was chosen
**Rationale**: Why
**Trade-offs**: Pros/cons
**Status**: Accepted / Superseded by #M