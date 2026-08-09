# MCP Tool Catalog

This document catalogs all 20 tools exposed by the two candidate-developed MCP servers. Each tool includes purpose, input/output schemas, authentication behavior, underlying operation, error handling, timeout/retry behavior, and example invocations.

---

## Alarm Management MCP Server (`alarm-management-mcp`)

**Base URL**: `http://alarm-mcp:9000/mcp` (Docker) / `http://localhost:9000/mcp` (local)
**Transport**: Streamable HTTP
**Authentication**: Bearer token propagated to upstream Alarm API (`demo-token`)
**Upstream**: Alarm API Simulator at `http://alarm-api:8000`
**Retry**: Max 3 attempts on 5xx/network errors
**Timeout**: 30 seconds per request

---

### 1. `search_assets`

**Purpose**: Search for assets by name or ID in the alarm management system.

**Input Schema**:
```json
{
  "query": "string (required) - Search query for asset name or ID",
  "limit": "integer (optional, default=10) - Maximum number of results"
}
```

**Output Schema**:
```json
{
  "results": [
    {
      "asset_id": "string",
      "asset_name": "string",
      "asset_type": "string",
      "criticality": "string",
      "unit": "string",
      "site": "string"
    }
  ]
}
```

**Authentication**: Bearer token passed to upstream `/assets/search`

**Underlying Operation**: `GET /assets/search?query={query}&limit={limit}`

**Error Behavior**:
- 4xx from upstream → propagated as MCP tool error
- 5xx/network → retry up to 3 times, then MCP tool error
- Invalid args → Pydantic validation error

**Timeout**: 30s (configurable via `REQUEST_TIMEOUT`)

**Example Invocation**:
```json
{"query": "Boiler Feed Pump", "limit": 5}
```

**Example Response**:
```json
{
  "results": [
    {
      "asset_id": "BFP-101",
      "asset_name": "Boiler Feed Pump 101",
      "asset_type": "pump",
      "criticality": "high",
      "unit": "Unit-1",
      "site": "Plant-A"
    }
  ]
}
```

---

### 2. `get_asset_metadata`

**Purpose**: Get detailed metadata for a specific asset.

**Input Schema**:
```json
{
  "asset_id": "string (required) - Asset ID"
}
```

**Output Schema**:
```json
{
  "asset_id": "string",
  "asset_name": "string",
  "asset_type": "string",
  "criticality": "string",
  "unit": "string",
  "site": "string",
  "location": "string",
  "manufacturer": "string",
  "model": "string",
  "install_date": "string"
}
```

**Authentication**: Bearer token passed to upstream `/assets/{asset_id}/metadata`

**Underlying Operation**: `GET /assets/{asset_id}/metadata`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"asset_id": "BFP-101"}
```

**Example Response**:
```json
{
  "asset_id": "BFP-101",
  "asset_name": "Boiler Feed Pump 101",
  "asset_type": "pump",
  "criticality": "high",
  "unit": "Unit-1",
  "site": "Plant-A",
  "location": "Boiler House",
  "manufacturer": "Flowserve",
  "model": "Mark III",
  "install_date": "2020-03-15"
}
```

---

### 3. `get_alarms`

**Purpose**: Retrieve alarms with comprehensive filtering and pagination.

**Input Schema**:
```json
{
  "asset_id": "string (optional) - Filter by asset ID",
  "unit": "string (optional) - Filter by unit",
  "site": "string (optional) - Filter by site",
  "severity": "string (optional) - Filter by severity (low, medium, high, critical)",
  "status": "string (optional) - Filter by status (active, acknowledged, cleared)",
  "alarm_name": "string (optional) - Filter by alarm name",
  "start_time": "string (optional, ISO format) - Start time",
  "end_time": "string (optional, ISO format) - End time",
  "page": "integer (optional, default=1) - Page number",
  "page_size": "integer (optional, default=50) - Page size",
  "sort_by": "string (optional, default=start_time) - Sort field",
  "sort_order": "string (optional, default=desc) - Sort order (asc/desc)"
}
```

**Output Schema**:
```json
{
  "total": "integer",
  "page": "integer",
  "page_size": "integer",
  "data": [
    {
      "alarm_id": "string",
      "asset_id": "string",
      "asset_name": "string",
      "alarm_name": "string",
      "severity": "string",
      "status": "string",
      "start_time": "string (ISO)",
      "end_time": "string (ISO)",
      "ack_time": "string (ISO)",
      "ack_user": "string",
      "description": "string"
    }
  ]
}
```

**Authentication**: Bearer token passed to upstream `/alarms`

**Underlying Operation**: `GET /alarms` with all filters as query params

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"asset_id": "BFP-101", "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-31T23:59:59Z", "page_size": 50}
```

**Example Response**:
```json
{
  "total": 42,
  "page": 1,
  "page_size": 50,
  "data": [
    {
      "alarm_id": "ALM-001",
      "asset_id": "BFP-101",
      "asset_name": "Boiler Feed Pump 101",
      "alarm_name": "High Discharge Pressure",
      "severity": "high",
      "status": "acknowledged",
      "start_time": "2024-01-15T10:30:00Z",
      "end_time": "2024-01-15T11:45:00Z",
      "ack_time": "2024-01-15T10:35:00Z",
      "ack_user": "operator1",
      "description": "Discharge pressure exceeded 150 bar"
    }
  ]
}
```

---

### 4. `get_alarm_by_id`

**Purpose**: Get a specific alarm by its unique ID.

**Input Schema**:
```json
{
  "alarm_id": "string (required) - Alarm ID"
}
```

**Output Schema**: Single alarm object (same structure as `get_alarms.data[0]`)

**Authentication**: Bearer token passed to upstream `/alarms/{alarm_id}`

**Underlying Operation**: `GET /alarms/{alarm_id}`

**Error Behavior**: Same as `search_assets`; 404 → "Alarm not found"

**Timeout**: 30s

**Example Invocation**:
```json
{"alarm_id": "ALM-001"}
```

---

### 5. `get_alarm_summary`

**Purpose**: Get alarm summary with KPIs grouped by specified fields.

**Input Schema**:
```json
{
  "time_range": {
    "start_time": "string (required, ISO format)",
    "end_time": "string (required, ISO format)"
  },
  "asset_ids": "array[string] (optional) - Filter by asset IDs",
  "unit": "string (optional) - Filter by unit",
  "site": "string (optional) - Filter by site",
  "severity": "array[string] (optional) - Filter by severity list",
  "group_by": "array[string] (optional, default=[\"alarm_name\"]) - Group by fields",
  "kpis": "array[string] (optional, default=[\"alarm_count\", \"recurring_rate\", \"avg_ack_delay\"]) - KPIs to calculate"
}
```

**Output Schema**:
```json
{
  "data": [
    {
      "group": {"alarm_name": "string"},
      "alarm_count": "integer",
      "recurring_rate": "float",
      "avg_ack_delay": "float (minutes)"
    }
  ]
}
```

**Authentication**: Bearer token passed to upstream `POST /alarms/summary`

**Underlying Operation**: `POST /alarms/summary` with JSON body

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{
  "time_range": {"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-31T23:59:59Z"},
  "asset_ids": ["BFP-101"],
  "severity": ["high", "critical"],
  "group_by": ["alarm_name"],
  "kpis": ["alarm_count", "recurring_rate", "avg_ack_delay"]
}
```

**Example Response**:
```json
{
  "data": [
    {
      "group": {"alarm_name": "High Discharge Pressure"},
      "alarm_count": 12,
      "recurring_rate": 0.85,
      "avg_ack_delay": 4.2
    }
  ]
}
```

---

### 6. `get_alarm_trends`

**Purpose**: Get alarm trends over time buckets.

**Input Schema**:
```json
{
  "time_range": {"start_time": "string", "end_time": "string"},
  "asset_ids": "array[string] (optional)",
  "unit": "string (optional)",
  "site": "string (optional)",
  "bucket": "string (optional, default=daily) - daily or hourly",
  "metrics": "array[string] (optional, default=[\"alarm_count\", \"avg_ack_delay\"])"
}
```

**Output Schema**:
```json
{
  "data": [
    {
      "bucket_start": "string (ISO)",
      "bucket_end": "string (ISO)",
      "alarm_count": "integer",
      "avg_ack_delay": "float"
    }
  ]
}
```

**Authentication**: Bearer token → `POST /alarms/trends`

**Underlying Operation**: `POST /alarms/trends`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"time_range": {"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-31T23:59:59Z"}, "bucket": "daily"}
```

---

### 7. `get_alarm_correlation`

**Purpose**: Get alarm correlations between assets using co-occurrence analysis.

**Input Schema**:
```json
{
  "asset_ids": "array[string] (required) - Asset IDs to correlate",
  "time_range": {"start_time": "string", "end_time": "string"},
  "correlation_method": "string (optional, default=cooccurrence)",
  "lag_window_minutes": "integer (optional, default=15)",
  "severity_threshold": "string (optional, default=medium)",
  "min_support": "integer (optional, default=1)"
}
```

**Output Schema**:
```json
{
  "correlations": [
    {
      "asset_a": "string",
      "asset_b": "string",
      "alarm_a": "string",
      "alarm_b": "string",
      "cooccurrence_count": "integer",
      "lag_minutes": "float"
    }
  ]
}
```

**Authentication**: Bearer token → `POST /alarms/correlation`

**Underlying Operation**: `POST /alarms/correlation`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{
  "asset_ids": ["BFP-101", "BFP-102"],
  "time_range": {"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-31T23:59:59Z"},
  "lag_window_minutes": 15
}
```

---

### 8. `get_flood_analysis`

**Purpose**: Analyze alarm floods in a unit.

**Input Schema**:
```json
{
  "unit": "string (required) - Unit to analyze",
  "time_range": {"start_time": "string", "end_time": "string"},
  "threshold_count": "integer (optional, default=10)",
  "rolling_window_minutes": "integer (optional, default=10)"
}
```

**Output Schema**:
```json
{
  "floods": [
    {
      "start_time": "string",
      "end_time": "string",
      "peak_count": "integer",
      "duration_minutes": "integer",
      "top_alarms": [{"alarm_name": "string", "count": "integer"}]
    }
  ]
}
```

**Authentication**: Bearer token → `POST /alarms/flood-analysis`

**Underlying Operation**: `POST /alarms/flood-analysis`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"unit": "Unit-1", "time_range": {"start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-31T23:59:59Z"}}
```

---

### 9. `get_rationalization_candidates`

**Purpose**: Get rationalization candidates for recurring/stale alarms.

**Input Schema**:
```json
{
  "time_range": {"start_time": "string", "end_time": "string"},
  "asset_ids": "array[string] (optional)",
  "unit": "string (optional)",
  "site": "string (optional)",
  "recurrence_threshold": "integer (optional, default=5)",
  "stale_minutes_threshold": "integer (optional, default=180)"
}
```

**Output Schema**:
```json
{
  "candidates": [
    {
      "alarm_name": "string",
      "asset_id": "string",
      "recurrence_count": "integer",
      "stale_minutes": "integer",
      "recommendation": "string"
    }
  ]
}
```

**Authentication**: Bearer token → `POST /alarms/rationalization-candidates`

**Underlying Operation**: `POST /alarms/rationalization-candidates`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

### 10. `get_priority_score`

**Purpose**: Calculate priority score for a specific alarm.

**Input Schema**:
```json
{
  "alarm_id": "string (required)"
}
```

**Output Schema**:
```json
{
  "alarm_id": "string",
  "priority_score": "float (0-100)",
  "factors": {
    "severity_weight": "float",
    "recurrence_weight": "float",
    "ack_delay_weight": "float"
  }
}
```

**Authentication**: Bearer token → `POST /alarms/priority-score`

**Underlying Operation**: `POST /alarms/priority-score`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

### 11. `get_operator_recommendations`

**Purpose**: Get operator action recommendations for an alarm.

**Input Schema**:
```json
{
  "alarm_id": "string (required)",
  "include_related": "boolean (optional, default=true)",
  "include_asset_context": "boolean (optional, default=true)",
  "include_historical_pattern": "boolean (optional, default=true)"
}
```

**Output Schema**:
```json
{
  "recommendations": [
    {
      "action": "string",
      "priority": "string",
      "rationale": "string",
      "related_alarms": ["string"]
    }
  ]
}
```

**Authentication**: Bearer token → `POST /recommendations/operator-actions`

**Underlying Operation**: `POST /recommendations/operator-actions`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

## Maintenance CMMS MCP Server (`maintenance-cmms-mcp`)

**Base URL**: `http://maintenance-mcp:9001/mcp` (Docker) / `http://localhost:9001/mcp` (local)
**Transport**: Streamable HTTP
**Authentication**: None (internal demo)
**Upstream**: CMMS API at `http://maintenance-cmms:8001`
**Retry**: Max 3 attempts on 5xx/network errors
**Timeout**: 30 seconds per request

---

### 12. `search_assets`

**Purpose**: Search for assets by name or ID in the CMMS.

**Input Schema**:
```json
{
  "query": "string (required) - Search query for asset name or ID",
  "limit": "integer (optional, default=10, min=1, max=100)"
}
```

**Output Schema**:
```json
{
  "results": [
    {
      "asset_id": "string",
      "asset_name": "string",
      "asset_type": "string",
      "criticality": "string",
      "unit": "string",
      "site": "string"
    }
  ]
}
```

**Authentication**: None

**Underlying Operation**: `GET /assets` (fetches all, filters client-side)

**Error Behavior**:
- 4xx/5xx → retry up to 3 times, then MCP tool error
- Network error → retry up to 3 times

**Timeout**: 30s

**Example Invocation**:
```json
{"query": "Compressor", "limit": 5}
```

**Example Response**:
```json
{
  "results": [
    {
      "asset_id": "COMP-201",
      "asset_name": "Compressor 201",
      "asset_type": "compressor",
      "criticality": "high",
      "unit": "Unit-2",
      "site": "Plant-A"
    }
  ]
}
```

---

### 13. `get_asset_metadata`

**Purpose**: Get detailed metadata for an asset from the CMMS.

**Input Schema**:
```json
{
  "asset_id": "string (required)"
}
```

**Output Schema**: Same as Alarm MCP `get_asset_metadata`

**Authentication**: None

**Underlying Operation**: `GET /assets/{asset_id}`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

### 14. `get_work_orders`

**Purpose**: Retrieve work orders with filtering and pagination from the CMMS.

**Input Schema**:
```json
{
  "asset_id": "string (optional)",
  "unit": "string (optional)",
  "site": "string (optional)",
  "status": "string (optional) - open, in_progress, completed, cancelled",
  "work_order_type": "string (optional) - preventive, corrective, predictive, inspection",
  "start_date": "string (optional, ISO format)",
  "end_date": "string (optional, ISO format)",
  "limit": "integer (optional, default=100, min=1, max=500)"
}
```

**Output Schema**:
```json
[
  {
    "work_order_id": "string",
    "asset_id": "string",
    "asset_name": "string",
    "work_order_type": "string",
    "status": "string",
    "description": "string",
    "created_date": "string (ISO)",
    "completed_date": "string (ISO)",
    "cost": "float",
    "assigned_to": "string"
  }
]
```

**Authentication**: None

**Underlying Operation**: `GET /work-orders` with query params

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"asset_id": "COMP-201", "status": "completed", "limit": 50}
```

---

### 15. `get_maintenance_logs`

**Purpose**: Retrieve maintenance activity logs with filtering and pagination.

**Input Schema**:
```json
{
  "asset_id": "string (optional)",
  "unit": "string (optional)",
  "site": "string (optional)",
  "activity_type": "string (optional)",
  "start_date": "string (optional, ISO format)",
  "end_date": "string (optional, ISO format)",
  "limit": "integer (optional, default=100, min=1, max=500)"
}
```

**Output Schema**:
```json
[
  {
    "log_id": "string",
    "asset_id": "string",
    "asset_name": "string",
    "activity_type": "string",
    "performed_date": "string (ISO)",
    "description": "string",
    "duration_hours": "float",
    "cost": "float",
    "performed_by": "string"
  }
]
```

**Authentication**: None

**Underlying Operation**: `GET /maintenance-logs` with query params

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

### 16. `get_asset_work_order_summary`

**Purpose**: Get work order summary KPIs for an asset.

**Input Schema**:
```json
{
  "asset_id": "string (required)",
  "days": "integer (optional, default=90) - Lookback period in days"
}
```

**Output Schema**:
```json
{
  "asset_id": "string",
  "total_orders": "integer",
  "open_orders": "integer",
  "completed_orders": "integer",
  "total_cost": "float"
}
```

**Authentication**: None

**Underlying Operation**: `GET /assets/{asset_id}/work-order-summary?days={days}`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

**Example Invocation**:
```json
{"asset_id": "COMP-201", "days": 180}
```

**Example Response**:
```json
{
  "asset_id": "COMP-201",
  "total_orders": 24,
  "open_orders": 2,
  "completed_orders": 22,
  "total_cost": 45750.00
}
```

---

### 17. `get_asset_maintenance_summary`

**Purpose**: Get maintenance activity summary KPIs for an asset.

**Input Schema**:
```json
{
  "asset_id": "string (required)",
  "days": "integer (optional, default=90)"
}
```

**Output Schema**:
```json
{
  "asset_id": "string",
  "total_activities": "integer",
  "total_hours": "float",
  "total_cost": "float"
}
```

**Authentication**: None

**Underlying Operation**: `GET /assets/{asset_id}/maintenance-summary?days={days}`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

### 18. `get_spare_parts`

**Purpose**: Retrieve spare parts inventory from the CMMS.

**Input Schema**:
```json
{
  "asset_id": "string (optional) - Filter by asset ID"
}
```

**Output Schema**:
```json
[
  {
    "part_id": "string",
    "asset_id": "string",
    "part_name": "string",
    "part_number": "string",
    "quantity_on_hand": "integer",
    "reorder_point": "integer",
    "unit_cost": "float",
    "criticality": "string"
  }
]
```

**Authentication**: None

**Underlying Operation**: `GET /spare-parts?asset_id={asset_id}`

**Error Behavior**: Same as `search_assets`

**Timeout**: 30s

---

## Running MCP Servers Independently

### Alarm Management MCP Server
```bash
cd mcp-servers/alarm-management
pip install -r requirements.txt
# Set environment variables (or use .env)
export ALARM_API_BASE_URL=http://localhost:8000
export ALARM_API_TOKEN=demo-token
python -m mcp_servers.alarm_management.server
# Server runs on http://localhost:9000/mcp
```

### Maintenance CMMS MCP Server
```bash
cd mcp-servers/maintenance
pip install -r requirements.txt
export CMMS_API_BASE_URL=http://localhost:8001
python -m mcp_servers.maintenance.server
# Server runs on http://localhost:9001/mcp
```

### Health Checks
```bash
curl http://localhost:9000/health  # Alarm MCP
curl http://localhost:9001/health  # Maintenance MCP
```

---

## Tool Discovery

Both servers support MCP tool discovery via `list_tools()`:

```python
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

async with streamablehttp_client("http://localhost:9000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        for tool in tools.tools:
            print(f"{tool.name}: {tool.description}")
```

---

## Observability

All tool invocations are traced in **LangSmith** with:
- `@traceable(run_type="tool", name="mcp_call_tool")` decorator
- Metadata: `mcp_server`, `tool_name`, `input`, `output`, `duration_ms`, `status`, `retry_count`, `error`
- Request/Trace ID correlation across frontend → backend → MCP → upstream API