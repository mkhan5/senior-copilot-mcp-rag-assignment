import os
import json
import uuid
import operator
import logging
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Annotated
from typing_extensions import TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from google import genai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Tool
from langsmith import traceable

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Maintenance Copilot Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MCP server URLs (streamable HTTP transport)
ALARM_MCP_URL = os.getenv("ALARM_MCP_URL", "http://localhost:9000/mcp")
MAINT_MCP_URL = os.getenv("MAINT_MCP_URL", "http://localhost:9001/mcp")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = "gemini-2.5-flash"
else:
    genai_client = None
    GEMINI_MODEL = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Dict[str, Any]] = []
    mcp_trace: List[Dict[str, Any]] = []
    query_plan: List[str] = []
    confidence: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# LangGraph state reducers
# ---------------------------------------------------------------------------

def _keep_first(a, b):
    """Keep the first non-empty value — used for write-once fields."""
    return a if a else b


def _replace(a, b):
    """Always use the latest value — used for query_plan, tool lists."""
    return b if b is not None else a


def _merge_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dicts; b overrides a for shared keys."""
    if not a:
        return b
    if not b:
        return a
    return {**a, **b}


# ---------------------------------------------------------------------------
# LangGraph state — TypedDict (required by LangGraph; @dataclass is not supported)
# ---------------------------------------------------------------------------

class CopilotState(TypedDict):
    user_query: Annotated[str, _keep_first]
    session_id: Annotated[str, _keep_first]
    intent: Annotated[Dict[str, Any], _merge_dict]
    # Tool name lists discovered from MCP servers — used for availability checks
    alarm_tool_names: Annotated[List[str], _replace]
    maint_tool_names: Annotated[List[str], _replace]
    alarm_mcp_results: Annotated[List[Dict[str, Any]], operator.add]
    maint_mcp_results: Annotated[List[Dict[str, Any]], operator.add]
    rag_results: Annotated[List[Dict[str, Any]], operator.add]
    final_answer: Annotated[str, _keep_first]
    citations: Annotated[List[Dict[str, Any]], operator.add]
    mcp_trace: Annotated[List[Dict[str, Any]], operator.add]
    query_plan: Annotated[List[str], operator.add]
    confidence: Annotated[float, _keep_first]
    history: Annotated[List[Dict[str, str]], operator.add]
    error: Annotated[Optional[str], _keep_first]


def _make_state(user_query: str, session_id: str, history: List[Dict[str, str]]) -> CopilotState:
    """Create a fresh CopilotState with safe defaults."""
    return CopilotState(
        user_query=user_query,
        session_id=session_id,
        intent={},
        alarm_tool_names=[],
        maint_tool_names=[],
        alarm_mcp_results=[],
        maint_mcp_results=[],
        rag_results=[],
        final_answer="",
        citations=[],
        mcp_trace=[],
        query_plan=[],
        confidence=0.0,
        history=history,
        error=None,
    )


# ---------------------------------------------------------------------------
# In-memory session store for multi-turn context retention
# Maps session_id -> list of {"role": "user"|"assistant", "content": str}
# ---------------------------------------------------------------------------
_session_store: Dict[str, List[Dict[str, str]]] = {}


# ---------------------------------------------------------------------------
# MCP client — per-request context managers (streamable HTTP transport)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def alarm_mcp_session():
    """Open a streamable-HTTP connection to the alarm MCP server, yield it, then close."""
    async with streamablehttp_client(ALARM_MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def maint_mcp_session():
    """Open a streamable-HTTP connection to the maintenance MCP server, yield it, then close."""
    async with streamablehttp_client(MAINT_MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@traceable(run_type="tool", name="mcp_call_tool")
async def _call_alarm_tool(session: ClientSession, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool error: {result.content[0].text if result.content else 'Unknown error'}")
    return json.loads(result.content[0].text)


@traceable(run_type="tool", name="mcp_call_tool")
async def _call_maint_tool(session: ClientSession, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool error: {result.content[0].text if result.content else 'Unknown error'}")
    return json.loads(result.content[0].text)


class RAGClient:
    def __init__(self):
        from rag.retrieval.retrieve import RetrievalService
        self.service = RetrievalService()

    def query(self, query: str, asset_id: Optional[str] = None) -> Dict[str, Any]:
        result = self.service.query(query, asset_id=asset_id)
        return {
            "answer": result.answer,
            "citations": result.citations,
            "confidence": result.confidence,
        }


rag_client = RAGClient()

@traceable(run_type="llm", name="gemini_generate")
def _gemini_generate(prompt: str) -> str:
    response = genai_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response


async def detect_intent(state: CopilotState) -> Dict:
    if not GEMINI_MODEL or not genai_client:
        return {"intent": {"assets": [], "time_range_days": 180, "query_type": "general",
                            "needs_alarms": True, "needs_maintenance": True, "needs_documents": True}}

    # Include recent conversation history for multi-turn context
    history = _session_store.get(state["session_id"], [])
    history_text = ""
    if history:
        history_text = "\n\nConversation history (most recent last):\n" + "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in history[-6:]
        )

    prompt = f"""Analyze this maintenance query and extract structured intent.

Query: "{state["user_query"]}"{history_text}

Available assets in the system:
- BFP-101: Boiler Feed Pump 101, criticality=high, type=pump
- BFP-102: Boiler Feed Pump 102, criticality=high, type=pump
- COMP-201: Compressor 201, criticality=high, type=compressor
- COMP-202: Compressor 202, criticality=medium, type=compressor
- MOTOR-301: Motor 301, criticality=medium, type=motor
- MOTOR-302: Motor 302, criticality=low, type=motor
- PUMP-401: Pump 401, criticality=high, type=pump
- PUMP-402: Pump 402, criticality=medium, type=pump

Return JSON with:
- assets: list of specific asset IDs/names mentioned. Leave EMPTY [] if the query asks about a category (e.g. "all pumps", "high-criticality assets") rather than a named asset.
- time_range_days: number of days to look back (default 180)
- query_type: one of ["alarm_analysis", "maintenance_history", "combined_analysis", "procedure_lookup", "spare_parts", "general"]
- needs_alarms: boolean — true if the query asks about alarms, recurring alarms, alarm history
- needs_maintenance: boolean — true if query_type is "combined_analysis", OR the query mentions causes, contributing factors, history, work orders, maintenance, repairs, recommendations, or intervention. Default true unless the query is purely about alarm counts or alarm names with no diagnostic intent.
- needs_documents: boolean — true if the query asks about manuals, procedures, recommendations, or likely causes
- needs_correlation: boolean — true only if the query explicitly asks to compare or correlate alarms between multiple named assets
- specific_alarms: list of alarm names/types if mentioned (e.g. ["High Vibration", "High Pressure"])

Only return valid JSON, no markdown fences."""

    try:
        response = _gemini_generate(prompt)
        intent = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
    except Exception as e:
        logger.warning("detect_intent: Gemini parse failed (%s), using defaults", e)
        intent = {"assets": [], "time_range_days": 180, "query_type": "general",
                  "needs_alarms": True, "needs_maintenance": True, "needs_documents": True}

    # Force needs_maintenance=True for combined_analysis — it always needs both sources
    if intent.get("query_type") == "combined_analysis":
        intent["needs_maintenance"] = True

    intent_summary = (
        f"query_type={intent.get('query_type')}, "
        f"assets={intent.get('assets', [])}, "
        f"time_range={intent.get('time_range_days')}d, "
        f"needs_alarms={intent.get('needs_alarms')}, "
        f"needs_maintenance={intent.get('needs_maintenance')}, "
        f"needs_documents={intent.get('needs_documents')}"
    )
    return {
        "intent": intent,
        "mcp_trace": [{"tool": "detect_intent", "server": "orchestrator",
                        "output": intent_summary, "timestamp": datetime.now().isoformat()}],
    }


async def discover_mcp_tools(state: CopilotState) -> Dict:
    """Open MCP sessions, list tools, store the tool names for availability checks."""
    alarm_tool_names: List[str] = []
    maint_tool_names: List[str] = []
    mcp_trace: List[Dict] = []
    error = None

    try:
        async with alarm_mcp_session() as session:
            result = await session.list_tools()
            alarm_tool_names = [t.name for t in result.tools]
        mcp_trace.append({"tool": "discover_tools", "server": "alarm-management",
                           "output": alarm_tool_names, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.exception("discover_mcp_tools: alarm MCP failed: %s", e)
        error = f"alarm MCP connection failed: {e}"
        mcp_trace.append({"tool": "discover_tools", "server": "alarm-management",
                           "error": str(e), "timestamp": datetime.now().isoformat()})

    try:
        async with maint_mcp_session() as session:
            result = await session.list_tools()
            maint_tool_names = [t.name for t in result.tools]
        mcp_trace.append({"tool": "discover_tools", "server": "maintenance-cmms",
                           "output": maint_tool_names, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.exception("discover_mcp_tools: maint MCP failed: %s", e)
        error = error or f"maint MCP connection failed: {e}"
        mcp_trace.append({"tool": "discover_tools", "server": "maintenance-cmms",
                           "error": str(e), "timestamp": datetime.now().isoformat()})

    return {
        "alarm_tool_names": alarm_tool_names,
        "maint_tool_names": maint_tool_names,
        "mcp_trace": mcp_trace,
        "error": error,
    }


async def plan_mcp_execution(state: CopilotState) -> Dict:
    """Emit routing decisions to query_plan. Does NOT duplicate tool calls — those go in mcp_trace."""
    intent = state["intent"]
    time_range_days = intent.get("time_range_days", 180)
    query_type = intent.get("query_type", "general")
    needs_alarms = intent.get("needs_alarms", True)
    needs_maintenance = intent.get("needs_maintenance", True)
    needs_documents = intent.get("needs_documents", True)
    assets = intent.get("assets", [])

    # Line 1: intent flags — all five shown explicitly so skips are visible
    flag_parts = [
        f"query_type={query_type}",
        f"time_range={time_range_days}d",
        f"alarms={'yes' if needs_alarms else 'SKIPPED'}",
        f"maintenance={'yes' if needs_maintenance else 'SKIPPED'}",
        f"rag={'yes' if needs_documents else 'SKIPPED'}",
    ]
    plan = [f"Intent: {', '.join(flag_parts)}"]

    # Line 2: routing decision
    route = []
    if needs_alarms:
        route.append("alarm tools")
    if needs_maintenance:
        route.append("maintenance tools")
    if needs_documents:
        route.append("RAG")
    route.append("synthesis")
    plan.append(f"Route: {' → '.join(route)}")

    # Line 3: asset scope
    if assets:
        plan.append(f"Asset scope: {', '.join(assets)} (named in query)")
    else:
        plan.append("Asset scope: all assets (category query — will filter by type/criticality)")

    return {"query_plan": plan}


async def _resolve_assets(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Resolve the working asset list from the intent.
    If specific assets are named, search for each one.
    If none are named, discover all assets and filter by criticality/type inferred from the query.
    Returns a list of asset dicts with at least {asset_id, asset_name, criticality, asset_type}.
    """
    named_assets = intent.get("assets", [])
    query_type = intent.get("query_type", "general")

    resolved: List[Dict[str, Any]] = []

    if named_assets:
        try:
            async with alarm_mcp_session() as session:
                for asset_name in named_assets:
                    try:
                        result = await _call_alarm_tool(session, "search_assets", {"query": asset_name, "limit": 5})
                        for r in result.get("results", []):
                            if r not in resolved:
                                resolved.append(r)
                    except Exception as e:
                        logger.warning("_resolve_assets: search for '%s' failed: %s", asset_name, e)
        except Exception as e:
            logger.warning("_resolve_assets: session open failed: %s", e)
    else:
        # Category query — search using known type keywords (empty string unreliable via MCP)
        user_query_lower = intent.get("_user_query", "").lower()
        want_high_crit = "high" in user_query_lower or "critical" in user_query_lower
        want_pumps = "pump" in user_query_lower
        want_compressors = "compressor" in user_query_lower
        want_motors = "motor" in user_query_lower

        # Build specific search terms; fall back to all known type names
        search_terms = []
        if want_pumps:
            search_terms.append("Pump")
        if want_compressors:
            search_terms.append("Compressor")
        if want_motors:
            search_terms.append("Motor")
        if not search_terms:
            search_terms = ["Boiler", "Compressor", "Motor", "Pump"]

        all_assets: List[Dict] = []
        seen_ids: set = set()
        try:
            async with alarm_mcp_session() as session:
                for term in search_terms:
                    try:
                        result = await _call_alarm_tool(session, "search_assets", {"query": term, "limit": 50})
                        for a in result.get("results", []):
                            if a["asset_id"] not in seen_ids:
                                seen_ids.add(a["asset_id"])
                                all_assets.append(a)
                    except Exception as e:
                        logger.warning("_resolve_assets: search term '%s' failed: %s", term, e)
        except Exception as e:
            logger.exception("_resolve_assets: broad search session failed: %s", e)

        logger.info("_resolve_assets: found %d assets via broad search: %s",
                    len(all_assets), [a["asset_id"] for a in all_assets])

        for asset in all_assets:
            crit_match = (not want_high_crit) or asset.get("criticality") in ("high", "critical")
            type_match = (
                (not (want_pumps or want_compressors or want_motors))
                or (want_pumps and asset.get("asset_type") == "pump")
                or (want_compressors and asset.get("asset_type") == "compressor")
                or (want_motors and asset.get("asset_type") == "motor")
            )
            if crit_match and type_match:
                resolved.append(asset)

        # Fallback: if filters matched nothing, return everything found
        if not resolved:
            resolved = all_assets

    return resolved


async def execute_alarm_tools(state: CopilotState) -> Dict:
    intent = state["intent"]
    intent["_user_query"] = state.get("user_query", "")
    time_range_days = intent.get("time_range_days", 180)
    end_time = datetime.now().isoformat() + "Z"
    start_time = (datetime.now() - timedelta(days=time_range_days)).isoformat() + "Z"

    working_assets = await _resolve_assets(intent)
    if not working_assets:
        logger.warning("execute_alarm_tools: no assets resolved")
        return {"alarm_mcp_results": [], "mcp_trace": [], "query_plan": ["Alarm tools: no assets resolved"]}

    alarm_mcp_results: List[Dict] = []
    # Trace: asset_discovery shows which assets were resolved and their criticality
    asset_discovery_output = ", ".join(
        f"{a['asset_id']} ({a.get('criticality', '?')} {a.get('asset_type', '')})"
        for a in working_assets
    )
    mcp_trace: List[Dict] = [
        {"tool": "asset_discovery", "server": "alarm-management",
         "output": asset_discovery_output,
         "timestamp": datetime.now().isoformat()}
    ]
    # Plan: routing decision only — no tool-call duplication
    query_plan: List[str] = [
        f"Alarm tools: {len(working_assets)} asset(s) in scope — "
        + ", ".join(f"{a['asset_id']} ({a.get('criticality','?')})" for a in working_assets)
    ]
    available = set(state.get("alarm_tool_names", []))

    try:
        async with alarm_mcp_session() as session:
            for asset in working_assets:
                asset_id = asset["asset_id"]
                asset_name = asset.get("asset_name", asset_id)
                try:
                    if "get_alarms" in available or not available:
                        alarms_result = await _call_alarm_tool(session, "get_alarms", {
                            "asset_id": asset_id, "start_time": start_time,
                            "end_time": end_time, "page_size": 50,
                        })
                        alarm_mcp_results.append({"tool": "get_alarms", "asset_id": asset_id,
                                                   "asset_name": asset_name,
                                                   "criticality": asset.get("criticality"),
                                                   "result": alarms_result})
                        # Trace: show total + top 3 alarm names by frequency
                        alarms_data = alarms_result.get("data", [])
                        top_names = Counter(a.get("alarm_name") for a in alarms_data).most_common(3)
                        top_str = ", ".join(f"{n} x{c}" for n, c in top_names) if top_names else "none"
                        mcp_trace.append({"tool": "get_alarms", "server": "alarm-management",
                                          "input": {"asset_id": asset_id, "time_range_days": time_range_days},
                                          "output": f"{alarms_result.get('total', 0)} alarms | top: {top_str}",
                                          "timestamp": datetime.now().isoformat()})

                    if "get_alarm_summary" in available or not available:
                        summary_result = await _call_alarm_tool(session, "get_alarm_summary", {
                            "asset_ids": [asset_id],
                            "time_range": {"start_time": start_time, "end_time": end_time},
                            "severity": ["high", "critical"],
                            "group_by": ["alarm_name"],
                            "kpis": ["alarm_count", "recurring_rate", "avg_ack_delay"],
                        })
                        alarm_mcp_results.append({"tool": "get_alarm_summary", "asset_id": asset_id,
                                                   "asset_name": asset_name,
                                                   "criticality": asset.get("criticality"),
                                                   "result": summary_result})
                        # Trace: show top recurring alarm with its KPIs
                        summary_items = summary_result.get("data", [])
                        top_item = max(summary_items, key=lambda x: x.get("alarm_count", 0), default=None)
                        if top_item:
                            top_name = top_item.get("group", {}).get("alarm_name", "?")
                            summary_str = (
                                f"{len(summary_items)} alarm type(s) | "
                                f"top: {top_name} "
                                f"(count={top_item.get('alarm_count',0)}, "
                                f"recurring_rate={top_item.get('recurring_rate') or 0:.2f}, "
                                f"avg_ack_delay={top_item.get('avg_ack_delay') or 0:.1f}min)"
                            )
                        else:
                            summary_str = "0 alarm types returned"
                        mcp_trace.append({"tool": "get_alarm_summary", "server": "alarm-management",
                                          "input": {"asset_ids": [asset_id]},
                                          "output": summary_str,
                                          "timestamp": datetime.now().isoformat()})
                except Exception as e:
                    logger.warning("execute_alarm_tools: asset %s failed: %s", asset_id, e)
                    mcp_trace.append({"tool": "error", "server": "alarm-management",
                                      "asset_id": asset_id, "error": str(e),
                                      "timestamp": datetime.now().isoformat()})

            # Correlation: only for explicitly named multiple assets
            named_assets = intent.get("assets", [])
            if intent.get("needs_correlation") and len(working_assets) >= 2 and named_assets:
                asset_ids = [a["asset_id"] for a in working_assets]
                try:
                    corr_result = await _call_alarm_tool(session, "get_alarm_correlation", {
                        "asset_ids": asset_ids,
                        "time_range": {"start_time": start_time, "end_time": end_time},
                    })
                    alarm_mcp_results.append({"tool": "get_alarm_correlation",
                                               "asset_ids": asset_ids, "result": corr_result})
                    corr_count = len(corr_result.get("correlations", []))
                    mcp_trace.append({"tool": "get_alarm_correlation", "server": "alarm-management",
                                      "input": {"asset_ids": asset_ids},
                                      "output": f"{corr_count} correlation pair(s) found",
                                      "timestamp": datetime.now().isoformat()})
                except Exception as e:
                    mcp_trace.append({"tool": "get_alarm_correlation", "server": "alarm-management",
                                      "error": str(e), "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.exception("execute_alarm_tools: session failed: %s", e)
        mcp_trace.append({"tool": "session_error", "server": "alarm-management",
                          "error": str(e), "timestamp": datetime.now().isoformat()})

    # Plan: count summary kept here as it summarises what actually ran (not a duplicate of trace content)
    alarm_count = sum(1 for r in alarm_mcp_results if r["tool"] == "get_alarms")
    summary_count = sum(1 for r in alarm_mcp_results if r["tool"] == "get_alarm_summary")
    query_plan.append(f"Alarm tools complete: {alarm_count} alarm fetch(es), {summary_count} summary(ies)")
    return {"alarm_mcp_results": alarm_mcp_results, "mcp_trace": mcp_trace, "query_plan": query_plan}


async def execute_maintenance_tools(state: CopilotState) -> Dict:
    intent = state["intent"]
    intent["_user_query"] = state["user_query"]
    time_range_days = intent.get("time_range_days", 180)

    working_assets = await _resolve_assets(intent)
    if not working_assets:
        logger.warning("execute_maintenance_tools: no assets resolved")
        return {"maint_mcp_results": [], "mcp_trace": [], "query_plan": ["Maintenance tools: no assets resolved"]}

    maint_mcp_results: List[Dict] = []
    mcp_trace: List[Dict] = []
    query_plan: List[str] = [
        f"Maintenance tools: {len(working_assets)} asset(s) in scope — "
        + ", ".join(a["asset_id"] for a in working_assets)
    ]

    try:
        async with maint_mcp_session() as session:
            for asset in working_assets:
                asset_id = asset["asset_id"]
                asset_name = asset.get("asset_name", asset_id)
                try:
                    wo_summary = await _call_maint_tool(session, "get_asset_work_order_summary",
                                                        {"asset_id": asset_id, "days": time_range_days})
                    maint_mcp_results.append({"tool": "get_asset_work_order_summary",
                                              "asset_id": asset_id, "asset_name": asset_name,
                                              "result": wo_summary})
                    wo_str = (
                        f"total={wo_summary.get('total_orders', 0)}, "
                        f"open={wo_summary.get('open_orders', 0)}, "
                        f"completed={wo_summary.get('completed_orders', 0)}, "
                        f"cost=${wo_summary.get('total_cost') or 0:.0f}"
                    )
                    mcp_trace.append({"tool": "get_asset_work_order_summary",
                                      "server": "maintenance-cmms",
                                      "input": {"asset_id": asset_id, "days": time_range_days},
                                      "output": wo_str, "timestamp": datetime.now().isoformat()})

                    maint_summary = await _call_maint_tool(session, "get_asset_maintenance_summary",
                                                           {"asset_id": asset_id, "days": time_range_days})
                    maint_mcp_results.append({"tool": "get_asset_maintenance_summary",
                                              "asset_id": asset_id, "asset_name": asset_name,
                                              "result": maint_summary})
                    ms_str = (
                        f"activities={maint_summary.get('total_activities', 0)}, "
                        f"hours={maint_summary.get('total_hours') or 0:.1f}, "
                        f"cost=${maint_summary.get('total_cost') or 0:.0f}"
                    )
                    mcp_trace.append({"tool": "get_asset_maintenance_summary",
                                      "server": "maintenance-cmms",
                                      "input": {"asset_id": asset_id, "days": time_range_days},
                                      "output": ms_str, "timestamp": datetime.now().isoformat()})

                    work_orders = await _call_maint_tool(session, "get_work_orders", {
                        "asset_id": asset_id,
                        "start_date": (datetime.now() - timedelta(days=time_range_days)).isoformat(),
                        "limit": 50,
                    })
                    maint_mcp_results.append({"tool": "get_work_orders", "asset_id": asset_id,
                                              "asset_name": asset_name, "result": work_orders})
                    mcp_trace.append({"tool": "get_work_orders", "server": "maintenance-cmms",
                                      "input": {"asset_id": asset_id},
                                      "output": f"{len(work_orders)} orders",
                                      "timestamp": datetime.now().isoformat()})

                    maint_logs = await _call_maint_tool(session, "get_maintenance_logs", {
                        "asset_id": asset_id,
                        "start_date": (datetime.now() - timedelta(days=time_range_days)).isoformat(),
                        "limit": 50,
                    })
                    maint_mcp_results.append({"tool": "get_maintenance_logs", "asset_id": asset_id,
                                              "asset_name": asset_name, "result": maint_logs})
                    mcp_trace.append({"tool": "get_maintenance_logs", "server": "maintenance-cmms",
                                      "input": {"asset_id": asset_id},
                                      "output": f"{len(maint_logs)} logs",
                                      "timestamp": datetime.now().isoformat()})
                except Exception as e:
                    logger.warning("execute_maintenance_tools: asset %s failed: %s", asset_id, e)
                    mcp_trace.append({"tool": "maintenance_mcp", "server": "maintenance-cmms",
                                      "asset_id": asset_id, "error": str(e),
                                      "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.exception("execute_maintenance_tools: session failed: %s", e)
        mcp_trace.append({"tool": "session_error", "server": "maintenance-cmms",
                          "error": str(e), "timestamp": datetime.now().isoformat()})

    wo_count = sum(1 for r in maint_mcp_results if r["tool"] == "get_work_orders")
    log_count = sum(1 for r in maint_mcp_results if r["tool"] == "get_maintenance_logs")
    query_plan.append(f"Maintenance tools complete: {wo_count} work order set(s), {log_count} log set(s)")
    return {"maint_mcp_results": maint_mcp_results, "mcp_trace": mcp_trace, "query_plan": query_plan}


async def query_rag(state: CopilotState) -> Dict:
    intent = state["intent"]
    intent["_user_query"] = state["user_query"]
    if not intent.get("needs_documents", True):
        return {"rag_results": [], "citations": [], "mcp_trace": []}

    query = state["user_query"]
    working_assets = await _resolve_assets(intent)

    rag_results: List[Dict] = []
    citations: List[Dict] = []
    mcp_trace: List[Dict] = []

    for asset in working_assets:
        asset_id = asset["asset_id"]
        try:
            rag_result = rag_client.query(query, asset_id=asset_id)
            rag_results.append({"asset": asset_id, "asset_name": asset.get("asset_name", asset_id),
                                 "result": rag_result})
            rag_cits = rag_result.get("citations", [])
            citations.extend(rag_cits)
            doc_names = ", ".join(
                dict.fromkeys(c.get("source", c.get("document", "?")) for c in rag_cits)
            ) or "no docs matched"
            mcp_trace.append({"tool": "rag_query", "server": "rag",
                               "input": {"asset_id": asset_id, "query": query[:80]},
                               "output": f"confidence={rag_result.get('confidence', 0):.2f} | docs: {doc_names}",
                               "timestamp": datetime.now().isoformat()})
        except Exception as e:
            logger.warning("query_rag: asset %s failed: %s", asset_id, e)
            mcp_trace.append({"tool": "rag_query", "server": "rag", "asset": asset_id,
                               "error": str(e), "timestamp": datetime.now().isoformat()})

    # General cross-asset RAG query
    try:
        rag_result = rag_client.query(query)
        rag_results.append({"asset": "general", "result": rag_result})
        rag_cits = rag_result.get("citations", [])
        citations.extend(rag_cits)
        doc_names = ", ".join(
            dict.fromkeys(c.get("source", c.get("document", "?")) for c in rag_cits)
        ) or "no docs matched"
        mcp_trace.append({"tool": "rag_query", "server": "rag",
                           "input": {"asset_id": "general", "query": query[:80]},
                           "output": f"confidence={rag_result.get('confidence', 0):.2f} | docs: {doc_names}",
                           "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.warning("query_rag: general query failed: %s", e)
        mcp_trace.append({"tool": "rag_query", "server": "rag", "asset": "general",
                           "error": str(e), "timestamp": datetime.now().isoformat()})

    asset_hits = sum(1 for r in rag_results if r.get("asset") != "general")
    return {
        "rag_results": rag_results,
        "citations": citations,
        "mcp_trace": mcp_trace,
        "query_plan": [f"RAG complete: {asset_hits} asset-specific + 1 general query, {len(citations)} citation(s)"],
    }


def _build_asset_context(alarm_results: List[Dict], maint_results: List[Dict]) -> str:
    """Build a structured per-asset context block for Gemini, avoiding raw JSON dumps."""
    # Group by asset_id
    assets: Dict[str, Dict] = {}

    for r in alarm_results:
        aid = r.get("asset_id")
        if not aid:
            continue
        if aid not in assets:
            assets[aid] = {
                "asset_name": r.get("asset_name", aid),
                "criticality": r.get("criticality", "unknown"),
                "alarms": [],
                "alarm_summaries": [],
            }
        tool = r.get("tool")
        if tool == "get_alarms":
            data = r.get("result", {})
            total = data.get("total", 0)
            alarms = data.get("data", [])
            assets[aid]["alarms"].append(f"  Total alarms: {total}")
            for a in alarms[:5]:  # top 5 examples
                assets[aid]["alarms"].append(
                    f"  - [{a.get('severity')}] {a.get('alarm_name')} at {a.get('start_time','?')[:10]}"
                )
        elif tool == "get_alarm_summary":
            data = r.get("result", {})
            for item in data.get("data", []):
                grp = item.get("group", {})
                assets[aid]["alarm_summaries"].append(
                    f"  - alarm_name={grp.get('alarm_name','?')}: "
                    f"count={item.get('alarm_count',0)}, "
                    f"recurring_rate={item.get('recurring_rate',0):.2f}, "
                    f"avg_ack_delay={item.get('avg_ack_delay',0):.1f}min"
                )

    for r in maint_results:
        aid = r.get("asset_id")
        if not aid:
            continue
        if aid not in assets:
            assets[aid] = {
                "asset_name": r.get("asset_name", aid),
                "criticality": "unknown",
                "alarms": [],
                "alarm_summaries": [],
            }
        assets[aid].setdefault("work_orders", [])
        assets[aid].setdefault("maint_logs", [])
        assets[aid].setdefault("wo_summary", {})
        assets[aid].setdefault("maint_summary", {})

        tool = r.get("tool")
        if tool == "get_asset_work_order_summary":
            assets[aid]["wo_summary"] = r.get("result", {})
        elif tool == "get_asset_maintenance_summary":
            assets[aid]["maint_summary"] = r.get("result", {})
        elif tool == "get_work_orders":
            orders = r.get("result", [])
            for o in orders[:3]:
                assets[aid]["work_orders"].append(
                    f"  - [{o.get('status')}] {o.get('work_order_type')} | {o.get('description','')[:60]} "
                    f"| cost=${o.get('cost',0):.0f} | completed={o.get('completed_date','pending')}"
                )
        elif tool == "get_maintenance_logs":
            logs = r.get("result", [])
            for lg in logs[:3]:
                assets[aid]["maint_logs"].append(
                    f"  - {lg.get('activity_type')} on {lg.get('performed_date','?')[:10]}: "
                    f"{lg.get('description','')[:60]} | {lg.get('duration_hours',0):.1f}h | cost=${lg.get('cost',0):.0f}"
                )

    # Render
    lines = []
    for aid, info in assets.items():
        lines.append(f"### Asset: {info['asset_name']} ({aid}) | Criticality: {info['criticality']}")
        if info.get("alarm_summaries"):
            lines.append("**Alarm Summary (recurring KPIs):**")
            lines.extend(info["alarm_summaries"])
        if info.get("alarms"):
            lines.append("**Recent Alarms:**")
            lines.extend(info["alarms"])
        wo = info.get("wo_summary", {})
        if wo:
            lines.append(
                f"**Work Order Summary:** total={wo.get('total_orders',0)}, "
                f"open={wo.get('open_orders',0)}, completed={wo.get('completed_orders',0)}, "
                f"total_cost=${wo.get('total_cost') or 0:.0f}"
            )
        ms = info.get("maint_summary", {})
        if ms:
            lines.append(
                f"**Maintenance Summary:** activities={ms.get('total_activities',0)}, "
                f"hours={ms.get('total_hours') or 0:.1f}, total_cost=${ms.get('total_cost') or 0:.0f}"
            )
        if info.get("work_orders"):
            lines.append("**Recent Work Orders:**")
            lines.extend(info["work_orders"])
        if info.get("maint_logs"):
            lines.append("**Recent Maintenance Logs:**")
            lines.extend(info["maint_logs"])
        lines.append("")

    return "\n".join(lines)


async def synthesize_answer(state: CopilotState) -> Dict:
    logger.info("synthesize_answer: entered. genai_client=%s, model=%s", genai_client, GEMINI_MODEL)
    if not GEMINI_MODEL or not genai_client:
        logger.warning("synthesize_answer: Gemini not configured — GEMINI_API_KEY may be missing.")
        return {"final_answer": "LLM not configured. Please set GEMINI_API_KEY.", "confidence": 0.0}

    asset_context = _build_asset_context(state["alarm_mcp_results"], state["maint_mcp_results"])
    rag_context = "\n".join([r["result"]["answer"] for r in state["rag_results"]])[:3000]

    has_data = bool(asset_context.strip())
    data_note = (
        "The asset context below contains real data retrieved from MCP tools. Use it to answer directly."
        if has_data
        else "No MCP data was retrieved. Explain this limitation and what data would be needed."
    )

    prompt = f"""You are a maintenance engineering copilot. Synthesize a comprehensive answer based on the following data sources.

User Query: {state["user_query"]}

{data_note}

Asset Data (from Alarm Management MCP + CMMS MCP — structured per asset):
{asset_context if asset_context.strip() else "[No asset data available]"}

Document Knowledge (from RAG):
{rag_context if rag_context.strip() else "[No document knowledge available]"}

Instructions:
1. Provide a clear, structured answer directly addressing the user's query
2. For each relevant asset, state: asset name, criticality, key alarm findings, and maintenance activity
3. If recurring_rate > 0 or alarm_count > 3, flag the asset as having recurring alarms
4. If work order total_cost > 0 or completed work orders exist in the period, flag recent maintenance
5. Cite document sources using [1], [2] etc. when RAG knowledge is used
6. Be specific and factual — use the numbers from the data above
7. Include a summary table or list of the qualifying assets at the end

Answer:"""

    try:
        response = _gemini_generate(prompt)
        final_answer = response.text
        logger.info("synthesize_answer: Gemini returned %d chars", len(response.text or ""))
        confidence = 0.8 if (state["alarm_mcp_results"] or state["maint_mcp_results"]) and state["rag_results"] else 0.5
    except Exception as e:
        logger.exception("synthesize_answer: Gemini call failed: %s", e)
        final_answer = f"Error generating answer: {e}"
        confidence = 0.0

    return {"final_answer": final_answer, "confidence": confidence}


# ---------------------------------------------------------------------------
# Conditional routing helpers
# ---------------------------------------------------------------------------

def _route_after_plan(state: CopilotState) -> str:
    """After planning, decide which branch to run first based on intent flags."""
    intent = state["intent"]
    if intent.get("needs_alarms", True):
        return "execute_alarm_tools"
    if intent.get("needs_maintenance", True):
        return "execute_maintenance_tools"
    if intent.get("needs_documents", True):
        return "query_rag"
    return "synthesize_answer"


def _route_after_alarms(state: CopilotState) -> str:
    """After alarm tools, decide whether to fetch maintenance data or skip to RAG."""
    intent = state["intent"]
    if intent.get("needs_maintenance", True):
        return "execute_maintenance_tools"
    if intent.get("needs_documents", True):
        return "query_rag"
    return "synthesize_answer"


def _route_after_maintenance(state: CopilotState) -> str:
    """After maintenance tools, decide whether to query RAG or skip to synthesis."""
    intent = state["intent"]
    if intent.get("needs_documents", True):
        return "query_rag"
    return "synthesize_answer"


# ---------------------------------------------------------------------------
# Build the LangGraph workflow with conditional routing
# ---------------------------------------------------------------------------
workflow = StateGraph(CopilotState)
workflow.add_node("detect_intent", detect_intent)
workflow.add_node("discover_mcp_tools", discover_mcp_tools)
workflow.add_node("plan_mcp_execution", plan_mcp_execution)
workflow.add_node("execute_alarm_tools", execute_alarm_tools)
workflow.add_node("execute_maintenance_tools", execute_maintenance_tools)
workflow.add_node("query_rag", query_rag)
workflow.add_node("synthesize_answer", synthesize_answer)

workflow.set_entry_point("detect_intent")
# Fixed sequential path: detect → connect → plan
workflow.add_edge("detect_intent", "discover_mcp_tools")
workflow.add_edge("discover_mcp_tools", "plan_mcp_execution")

# Conditional: skip alarm/maintenance/rag nodes if the intent doesn't need them
workflow.add_conditional_edges(
    "plan_mcp_execution",
    _route_after_plan,
    {
        "execute_alarm_tools": "execute_alarm_tools",
        "execute_maintenance_tools": "execute_maintenance_tools",
        "query_rag": "query_rag",
        "synthesize_answer": "synthesize_answer",
    },
)
workflow.add_conditional_edges(
    "execute_alarm_tools",
    _route_after_alarms,
    {
        "execute_maintenance_tools": "execute_maintenance_tools",
        "query_rag": "query_rag",
        "synthesize_answer": "synthesize_answer",
    },
)
workflow.add_conditional_edges(
    "execute_maintenance_tools",
    _route_after_maintenance,
    {
        "query_rag": "query_rag",
        "synthesize_answer": "synthesize_answer",
    },
)
workflow.add_edge("query_rag", "synthesize_answer")
workflow.add_edge("synthesize_answer", END)

copilot_graph = workflow.compile()


@app.on_event("startup")
async def startup():
    logger.info("startup: copilot-backend ready (MCP sessions are opened per-request)")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "copilot-backend"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    prior_history = _session_store.get(session_id, [])
    initial_state = _make_state(request.message, session_id, prior_history)

    try:
        final_state = await copilot_graph.ainvoke(
            initial_state,
            config={
                "run_name": "copilot_chat",
                "metadata": {"session_id": session_id},
                "tags": [f"session:{session_id}"],
            },
        )

        # LangGraph with TypedDict always returns a dict
        final_answer = final_state.get("final_answer", "")
        citations = final_state.get("citations", [])
        mcp_trace = final_state.get("mcp_trace", [])
        query_plan = final_state.get("query_plan", [])
        confidence = final_state.get("confidence", 0.0)

        # Persist this turn to the session store (keep last 20 turns)
        history = _session_store.setdefault(session_id, [])
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": final_answer})
        _session_store[session_id] = history[-20:]

        return ChatResponse(
            session_id=session_id,
            answer=final_answer,
            citations=citations,
            mcp_trace=mcp_trace,
            query_plan=query_plan,
            confidence=confidence,
        )
    except Exception as e:
        logger.exception("chat: unhandled exception for session %s: %s", session_id, e)
        return ChatResponse(
            session_id=session_id,
            answer=f"Error processing request: {str(e)}",
            citations=[],
            mcp_trace=[],
            query_plan=[],
            confidence=0.0,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)