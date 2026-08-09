import os
import json
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from fastmcp import FastMCP


class Settings(BaseSettings):
    alarm_api_base_url: str = "http://alarm-api:8000"
    alarm_api_token: str = "demo-token"
    request_timeout: float = 30.0
    max_retries: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


settings = Settings()

client = httpx.AsyncClient(
    base_url=settings.alarm_api_base_url,
    headers={"Authorization": f"Bearer {settings.alarm_api_token}"},
    timeout=settings.request_timeout,
)


async def _request_with_retry(method: str, path: str, **kwargs) -> httpx.Response:
    last_error = None
    for attempt in range(settings.max_retries):
        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            last_error = e
        except httpx.RequestError as e:
            last_error = e
    raise last_error or Exception("Request failed after retries")


# ---------------------------------------------------------------------------
# Pydantic arg models
# ---------------------------------------------------------------------------

class SearchAssetsArgs(BaseModel):
    query: str = Field(description="Search query for asset name or ID")
    limit: int = Field(default=10, description="Maximum number of results")


class GetAssetMetadataArgs(BaseModel):
    asset_id: str = Field(description="Asset ID")


class GetAlarmsArgs(BaseModel):
    asset_id: Optional[str] = Field(default=None, description="Filter by asset ID")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    severity: Optional[str] = Field(default=None, description="Filter by severity")
    status: Optional[str] = Field(default=None, description="Filter by status")
    alarm_name: Optional[str] = Field(default=None, description="Filter by alarm name")
    start_time: Optional[str] = Field(default=None, description="Start time (ISO format)")
    end_time: Optional[str] = Field(default=None, description="End time (ISO format)")
    page: int = Field(default=1, description="Page number")
    page_size: int = Field(default=50, description="Page size")
    sort_by: str = Field(default="start_time", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order")


class GetAlarmByIdArgs(BaseModel):
    alarm_id: str = Field(description="Alarm ID")


class AlarmSummaryArgs(BaseModel):
    asset_ids: Optional[List[str]] = Field(default=None, description="Filter by asset IDs")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    time_range: Dict[str, str] = Field(description="Time range with start_time and end_time")
    severity: Optional[List[str]] = Field(default=None, description="Filter by severity")
    group_by: List[str] = Field(default=["alarm_name"], description="Group by fields")
    kpis: List[str] = Field(default=["alarm_count", "recurring_rate", "avg_ack_delay"], description="KPIs to calculate")


class AlarmTrendsArgs(BaseModel):
    asset_ids: Optional[List[str]] = Field(default=None, description="Filter by asset IDs")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    time_range: Dict[str, str] = Field(description="Time range with start_time and end_time")
    bucket: str = Field(default="daily", description="Time bucket (daily, hourly)")
    metrics: List[str] = Field(default=["alarm_count", "avg_ack_delay"], description="Metrics to compute")


class CorrelationArgs(BaseModel):
    asset_ids: List[str] = Field(description="Asset IDs to correlate")
    time_range: Dict[str, str] = Field(description="Time range with start_time and end_time")
    correlation_method: str = Field(default="cooccurrence", description="Correlation method")
    lag_window_minutes: int = Field(default=15, description="Lag window in minutes")
    severity_threshold: str = Field(default="medium", description="Minimum severity")
    min_support: int = Field(default=1, description="Minimum support count")


class FloodAnalysisArgs(BaseModel):
    unit: str = Field(description="Unit to analyze")
    time_range: Dict[str, str] = Field(description="Time range with start_time and end_time")
    threshold_count: int = Field(default=10, description="Alarm count threshold")
    rolling_window_minutes: int = Field(default=10, description="Rolling window in minutes")


class RationalizationArgs(BaseModel):
    asset_ids: Optional[List[str]] = Field(default=None, description="Filter by asset IDs")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    time_range: Dict[str, str] = Field(description="Time range with start_time and end_time")
    recurrence_threshold: int = Field(default=5, description="Minimum recurrence count")
    stale_minutes_threshold: int = Field(default=180, description="Stale threshold in minutes")


class PriorityScoreArgs(BaseModel):
    alarm_id: str = Field(description="Alarm ID")


class RecommendationArgs(BaseModel):
    alarm_id: str = Field(description="Alarm ID")
    include_related: bool = Field(default=True, description="Include related alarms")
    include_asset_context: bool = Field(default=True, description="Include asset context")
    include_historical_pattern: bool = Field(default=True, description="Include historical patterns")


# ---------------------------------------------------------------------------
# FastMCP server + tools
# ---------------------------------------------------------------------------

mcp = FastMCP("alarm-management-mcp")


@mcp.tool()
async def search_assets(query: str, limit: int = 10) -> str:
    """Search for assets by name or ID."""
    response = await _request_with_retry("GET", "/assets/search", params={"query": query, "limit": limit})
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_asset_metadata(asset_id: str) -> str:
    """Get detailed metadata for an asset."""
    response = await _request_with_retry("GET", f"/assets/{asset_id}/metadata")
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_alarms(
    asset_id: Optional[str] = None, unit: Optional[str] = None, site: Optional[str] = None,
    severity: Optional[str] = None, status: Optional[str] = None, alarm_name: Optional[str] = None,
    start_time: Optional[str] = None, end_time: Optional[str] = None,
    page: int = 1, page_size: int = 50, sort_by: str = "start_time", sort_order: str = "desc",
) -> str:
    """Retrieve alarms with filtering and pagination."""
    args = GetAlarmsArgs(
        asset_id=asset_id, unit=unit, site=site, severity=severity, status=status,
        alarm_name=alarm_name, start_time=start_time, end_time=end_time,
        page=page, page_size=page_size, sort_by=sort_by, sort_order=sort_order,
    )
    params_dict = {k: v for k, v in args.model_dump().items() if v is not None}
    response = await _request_with_retry("GET", "/alarms", params=params_dict)
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_alarm_by_id(alarm_id: str) -> str:
    """Get a specific alarm by ID."""
    response = await _request_with_retry("GET", f"/alarms/{alarm_id}")
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_alarm_summary(
    time_range: Dict[str, str],
    asset_ids: Optional[List[str]] = None, unit: Optional[str] = None, site: Optional[str] = None,
    severity: Optional[List[str]] = None,
    group_by: List[str] = ["alarm_name"],
    kpis: List[str] = ["alarm_count", "recurring_rate", "avg_ack_delay"],
) -> str:
    """Get alarm summary with KPIs grouped by specified fields."""
    args = AlarmSummaryArgs(
        asset_ids=asset_ids, unit=unit, site=site, time_range=time_range,
        severity=severity, group_by=group_by, kpis=kpis,
    )
    response = await _request_with_retry("POST", "/alarms/summary", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_alarm_trends(
    time_range: Dict[str, str],
    asset_ids: Optional[List[str]] = None, unit: Optional[str] = None, site: Optional[str] = None,
    bucket: str = "daily", metrics: List[str] = ["alarm_count", "avg_ack_delay"],
) -> str:
    """Get alarm trends over time buckets."""
    args = AlarmTrendsArgs(
        asset_ids=asset_ids, unit=unit, site=site, time_range=time_range, bucket=bucket, metrics=metrics,
    )
    response = await _request_with_retry("POST", "/alarms/trends", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_alarm_correlation(
    asset_ids: List[str], time_range: Dict[str, str],
    correlation_method: str = "cooccurrence", lag_window_minutes: int = 15,
    severity_threshold: str = "medium", min_support: int = 1,
) -> str:
    """Get alarm correlations between assets using co-occurrence."""
    args = CorrelationArgs(
        asset_ids=asset_ids, time_range=time_range, correlation_method=correlation_method,
        lag_window_minutes=lag_window_minutes, severity_threshold=severity_threshold, min_support=min_support,
    )
    response = await _request_with_retry("POST", "/alarms/correlation", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_flood_analysis(
    unit: str, time_range: Dict[str, str],
    threshold_count: int = 10, rolling_window_minutes: int = 10,
) -> str:
    """Analyze alarm floods in a unit."""
    args = FloodAnalysisArgs(
        unit=unit, time_range=time_range, threshold_count=threshold_count,
        rolling_window_minutes=rolling_window_minutes,
    )
    response = await _request_with_retry("POST", "/alarms/flood-analysis", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_rationalization_candidates(
    time_range: Dict[str, str],
    asset_ids: Optional[List[str]] = None, unit: Optional[str] = None, site: Optional[str] = None,
    recurrence_threshold: int = 5, stale_minutes_threshold: int = 180,
) -> str:
    """Get rationalization candidates for recurring/stale alarms."""
    args = RationalizationArgs(
        asset_ids=asset_ids, unit=unit, site=site, time_range=time_range,
        recurrence_threshold=recurrence_threshold, stale_minutes_threshold=stale_minutes_threshold,
    )
    response = await _request_with_retry("POST", "/alarms/rationalization-candidates", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_priority_score(alarm_id: str) -> str:
    """Calculate priority score for an alarm."""
    response = await _request_with_retry("POST", "/alarms/priority-score", json={"alarm_id": alarm_id})
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_operator_recommendations(
    alarm_id: str, include_related: bool = True,
    include_asset_context: bool = True, include_historical_pattern: bool = True,
) -> str:
    """Get operator action recommendations for an alarm."""
    args = RecommendationArgs(
        alarm_id=alarm_id, include_related=include_related,
        include_asset_context=include_asset_context, include_historical_pattern=include_historical_pattern,
    )
    response = await _request_with_retry("POST", "/recommendations/operator-actions", json=args.model_dump())
    return json.dumps(response.json(), indent=2)


# ---------------------------------------------------------------------------
# Plain /health endpoint for Docker healthcheck
# ---------------------------------------------------------------------------

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    try:
        await client.get("/health")
        upstream = "ok"
    except Exception:
        upstream = "unreachable"
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "upstream_alarm_api": upstream})


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)
