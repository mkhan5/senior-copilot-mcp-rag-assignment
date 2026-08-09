# RAG Design Document

## Overview

The Retrieval-Augmented Generation (RAG) pipeline provides grounded, citation-backed answers from maintenance documentation. It operates as a first-class component within the LangGraph workflow, participating in the same end-to-end trace as MCP tool calls.

---

## Source Document Corpus

| Document | Type | Asset Focus | Chunks (est.) |
|----------|------|-------------|---------------|
| `boiler_feed_pump_101_manual.md` | Equipment Manual | BFP-101, BFP-102 | ~40 |
| `compressor_201_manual.md` | Equipment Manual | COMP-201, COMP-202 | ~35 |
| `motor_maintenance_procedure.md` | Maintenance Procedure | MOTOR-301, MOTOR-302 | ~25 |
| `pump_inspection_checklist.md` | Inspection Checklist | All pumps | ~15 |
| `spare_parts_guidance.md` | Spare Parts Guidance | All assets | ~20 |

**Total**: ~135 chunks across 5 documents

---

## Ingestion Flow

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────┐
│  Documents  │────▶│   Loader    │────▶│   Splitter   │────▶│  Embedder   │────▶│ ChromaDB    │
│  (markdown) │     │  (md/txt/   │     │ (Recursive   │     │ (all-MiniLM-│     │ (Persistent │
│             │     │   pdf)      │     │  CharText    │     │  L6-v2)     │     │  Client)    │
└─────────────┘     └─────────────┘     └──────────────┘     └─────────────┘     └─────────────┘
                           │                    │                    │
                           ▼                    ▼                    ▼
                    ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
                    │  Metadata   │     │ chunk_size=500│     │ cosine      │
                    │ Extraction  │     │ overlap=50   │     │ similarity  │
                    │ (asset_id,  │     │ separators:  │     │ collection: │
                    │  doc_type)  │     │ ##, ###,     │     │ maintenance_│
                    └─────────────┘     └──────────────┘     └─────────────┘
```

### Ingestion Script
**Location**: `rag/ingestion/ingest.py`
**Class**: `DocumentIngestion`
**Command**: `docker-compose run --rm rag-ingestion` or `python ingest.py`

### Configuration (Environment Variables)
| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMENTS_DIR` | `rag/documents` | Source document directory |
| `PERSIST_DIR` | `rag/chroma_db` | ChromaDB persistence directory |
| `COLLECTION_NAME` | `maintenance_docs` | ChromaDB collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |

---

## Text Extraction

- **Markdown (`.md`)**: Read as UTF-8 text, preserved as-is
- **Text (`.txt`)**: Read as UTF-8 text
- **PDF (`.pdf`)**: `pypdf.PdfReader` page-by-page extraction, concatenated with newlines
- **Unsupported types**: Raise `ValueError`

---

## Chunking Strategy

**Splitter**: `langchain_text_splitters.RecursiveCharacterTextSplitter`

```python
RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]
)
```

**Rationale**:
- `chunk_size=500`: Fits within Gemini context window with multiple chunks + prompt
- `chunk_overlap=50`: Preserves context across boundaries
- Hierarchical separators: Respects markdown heading structure (##, ###, ####) → paragraphs → sentences → characters

---

## Chunk Metadata

Each chunk receives enriched metadata:

| Field | Source | Example |
|-------|--------|---------|
| `source` | Filename | `boiler_feed_pump_101_manual.md` |
| `asset_id` | Extracted from content | `BFP-101` |
| `asset_name` | Extracted from content | `Boiler Feed Pump 101` |
| `doc_type` | Filename heuristic | `equipment_manual` |
| `file_path` | Absolute path | `rag/documents/boiler_feed_pump_101_manual.md` |
| `chunk_index` | Sequential per doc | `0`, `1`, `2`... |
| `chunk_count` | Total chunks in doc | `42` |

**Metadata Extraction Logic** (`extract_metadata`):
1. Scans first 20 lines for `asset_id`/`asset name` patterns
2. Infers `doc_type` from filename keywords:
   - `manual` → `equipment_manual`
   - `procedure`/`sop` → `maintenance_procedure`
   - `checklist` → `inspection_checklist`
   - `spare` → `spare_parts_guidance`
   - `troubleshoot` → `troubleshooting_guide`
   - default → `general`

**ChromaDB Compatibility**: All metadata values converted to strings (ChromaDB requirement)

---

## Embedding Model

| Property | Value |
|----------|-------|
| **Model** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Dimensions** | 384 |
| **Source** | Hugging Face Hub (auto-downloaded on first run) |
| **Similarity** | Cosine (configured in ChromaDB collection metadata) |
| **Batch Encoding** | `embedder.encode(texts, show_progress_bar=True)` |

**Rationale**: Lightweight (22M params), fast inference, strong semantic retrieval for technical domains, no GPU required.

---

## Vector Database

| Property | Value |
|----------|-------|
| **Database** | ChromaDB 0.5+ |
| **Client** | `PersistentClient` (file-based, no separate server) |
| **Path** | `rag/chroma_db/` |
| **Collection** | `maintenance_docs` |
| **Distance Metric** | Cosine (`hnsw:space: cosine`) |
| **Index Type** | HNSW (default) |

---

## Retrieval

### Service Class
**Location**: `rag/retrieval/retrieve.py`
**Class**: `RetrievalService`

### Configuration
| Parameter | Default | Env Var |
|-----------|---------|---------|
| `top_k` | 5 | `TOP_K` |
| `score_threshold` | 0.3 | `SCORE_THRESHOLD` |

### Query Method
```python
def retrieve(
    self,
    query: str,
    asset_id: Optional[str] = None,
    doc_type: Optional[str] = None,
    top_k: Optional[int] = None,
) -> List[RetrievalResult]
```

### Metadata Filters
- `asset_id`: Exact match on chunk metadata
- `doc_type`: Exact match on chunk metadata
- Combined with `$and` logic in ChromaDB `where` filter

### Scoring
- ChromaDB returns `distance` (cosine distance: 0 = identical, 2 = opposite)
- **Score** = `1 - distance` (converts to similarity: 1 = identical, -1 = opposite)
- **Threshold**: Only results with `score >= score_threshold` (default 0.3) returned

### Output: `RetrievalResult`
```python
@dataclass
class RetrievalResult:
    content: str           # Chunk text
    metadata: Dict         # Full chunk metadata
    score: float           # Similarity score (0-1)
    citation_id: str       # "[1]", "[2]", etc.
```

---

## Prompt Injection Protection

**Location**: `_check_prompt_injection()` in `RetrievalService`

**Patterns Detected** (12):
- `ignore previous instructions`
- `ignore all instructions`
- `system prompt`
- `you are now`
- `pretend to be`
- `roleplay`
- `disregard`
- `override`
- `new instructions`

**Behavior**: Logs warning, continues processing (does not block). Designed for observability, not hard blocking.

---

## Grounded Generation

### LLM
- **Model**: `gemini-2.5-flash` (via Google GenAI SDK)
- **Temperature**: Default (not explicitly set)

### Prompt Template
```
You are a maintenance engineering assistant. Answer the user's question using ONLY the provided context from maintenance documents.

Context:
{context}

Question: {query}

Instructions:
1. Answer based ONLY on the provided context
2. Cite sources using the citation IDs like [1], [2], etc.
3. If the context doesn't contain enough information, say so clearly
4. Do not add information not in the context
5. Be concise and specific
6. Include actionable recommendations when applicable

Answer:
```

### Context Building (`_build_context`)
Each result formatted as:
```
[1] Source: boiler_feed_pump_101_manual.md | Asset: Boiler Feed Pump 101 | Type: equipment_manual
{chunk_content}

---
 
[2] Source: ...
```

### Citation Building (`_build_citations`)
```json
[
  {
    "citation_id": "[1]",
    "source": "boiler_feed_pump_101_manual.md",
    "asset_id": "BFP-101",
    "asset_name": "Boiler Feed Pump 101",
    "doc_type": "equipment_manual",
    "score": 0.847,
    "chunk_index": "3"
  }
]
```

### Confidence Calculation
```
confidence = min(avg_retrieval_score * 1.2, 1.0)
```
- No results → 0.0
- No Gemini API key → 0.5 (fallback)
- Error during generation → 0.3 (with partial context)

### Output: `GroundedAnswer`
```python
@dataclass
class GroundedAnswer:
    answer: str              # LLM-generated answer with [1], [2] citations
    citations: List[Dict]    # Structured citations
    confidence: float        # 0.0 - 1.0
    query: str               # Original query
```

---

## Integration with LangGraph Workflow

### Node: `query_rag`
- Called conditionally based on `intent.needs_documents`
- Queries per resolved asset + 1 general cross-asset query
- Results → `rag_results`, `citations`, `mcp_trace`
- Trace entry includes: `tool=rag_query`, `server=rag`, `input={asset_id, query}`, `output={confidence, docs}`

### Synthesis Node
- Receives `rag_results` + `alarm_mcp_results` + `maint_mcp_results`
- Combines asset data + RAG context in single prompt
- Final answer includes inline `[1]`, `[2]` citations from RAG

---

## Index Refresh Process

**Current**: Batch ingestion job (run once at startup or manually)
```bash
docker-compose run --rm rag-ingestion
```

**Production Considerations**:
- Incremental updates: Track file mtimes, only re-process changed files
- Scheduled refresh: Cron job or Kubernetes CronJob
- Triggered refresh: File watcher or API endpoint
- Blue-green: Build new collection, swap alias on success

---

## Retrieval Tests

**Location**: `rag/tests/` (to be created)
**Test Coverage**:
- Document ingestion → chunk count verification
- Chunking → correct size/overlap, metadata preservation
- Metadata capture → asset_id, doc_type populated
- Retrieval relevance → known queries return expected chunks
- Citation correctness → citation_id matches retrieved chunk
- No-result behavior → confidence=0, helpful message
- Prompt-injection handling → warning logged, processing continues

---

## Example Retrieved Chunks

**Query**: "What are the alarm response procedures for high discharge pressure on Boiler Feed Pump 101?"

**Top Result** (score: 0.89):
```
[1] Source: boiler_feed_pump_101_manual.md | Asset: Boiler Feed Pump 101 | Type: equipment_manual
## Alarm Response: High Discharge Pressure (ALM-HDP-001)

**Trigger**: Discharge pressure > 150 bar for > 30 seconds

**Immediate Actions**:
1. Verify pressure reading on local gauge (PI-101)
2. Check discharge valve position (should be 100% open)
3. Reduce pump speed by 10% via VFD
4. If pressure remains high after 2 minutes, initiate controlled shutdown

**Escalation**: Notify shift supervisor if pressure > 165 bar
**Reference**: Section 7.3.2, BFP-101 Operations Manual Rev 3
```

---

## Citation Examples

**In Answer**:
> "For BFP-101, the high discharge pressure alarm (ALM-HDP-001) triggers at 150 bar. The immediate response is to verify the local gauge PI-101 and check discharge valve position [1]. If pressure persists, reduce pump speed by 10% via VFD [1]."

**Structured Citation Output**:
```json
{
  "citation_id": "[1]",
  "source": "boiler_feed_pump_101_manual.md",
  "asset_id": "BFP-101",
  "asset_name": "Boiler Feed Pump 101",
  "doc_type": "equipment_manual",
  "score": 0.89,
  "chunk_index": "7"
}
```

---

## Low-Confidence Handling

| Scenario | Behavior |
|----------|----------|
| No chunks above threshold | Returns "I could not find relevant information..." with confidence=0.0 |
| Chunks found but low scores | Generates answer with confidence < 0.5, notes limitation |
| Gemini API unavailable | Fallback: returns raw context (truncated) with confidence=0.5 |
| Generation error | Returns error message + partial context with confidence=0.3 |

---

## Reproducibility

- **Fixed Embedding Model**: `all-MiniLM-L6-v2` (deterministic)
- **Fixed Chunking**: Deterministic splitter with fixed separators
- **Fixed Chunk IDs**: `{filename}_{chunk_index}` (stable across runs)
- **ChromaDB Persistence**: Same directory → same index
- **Temperature**: Not set (Gemini default, may vary slightly)

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Prompt injection in docs | Detection + logging (12 patterns) |
| Retrieved document trust | Only committed markdown files in repo |
| Secret leakage in chunks | No secrets in source documents |
| PII in maintenance logs | Not in RAG corpus (separate MCP) |
| LLM output validation | Citations required, grounded prompt |

---

## Performance

| Metric | Target |
|--------|--------|
| Ingestion (5 docs) | < 30 seconds |
| Retrieval latency | < 500ms (embed + search) |
| Generation latency | < 3s (Gemini API) |
| End-to-end RAG query | < 4s |
| Index size (5 docs) | ~500 KB |