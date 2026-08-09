import json
import httpx
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from fastmcp import FastMCP

from .config import settings


# ---------------------------------------------------------------------------
# HTTP client — talks to the maintenance-cmms HTTP API
# ---------------------------------------------------------------------------
client = httpx.AsyncClient(
    base_url=settings.cmms_api_base_url,
    timeout=settings.request_timeout,
)


async def _request_with_retry(method: str, path: str, **kwargs) -> httpx.Response:
    """Retry up to max_retries times on 5xx or network errors."""
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
    limit: int = Field(default=10, description="Maximum number of results", ge=1, le=100)


class GetWorkOrdersArgs(BaseModel):
    asset_id: Optional[str] = Field(default=None, description="Filter by asset ID")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    status: Optional[str] = Field(default=None, description="Filter by status")
    work_order_type: Optional[str] = Field(default=None, description="Filter by work order type")
    start_date: Optional[str] = Field(default=None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(default=None, description="End date (ISO format)")
    limit: int = Field(default=100, description="Maximum number of results", ge=1, le=500)


class GetMaintenanceLogsArgs(BaseModel):
    asset_id: Optional[str] = Field(default=None, description="Filter by asset ID")
    unit: Optional[str] = Field(default=None, description="Filter by unit")
    site: Optional[str] = Field(default=None, description="Filter by site")
    activity_type: Optional[str] = Field(default=None, description="Filter by activity type")
    start_date: Optional[str] = Field(default=None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(default=None, description="End date (ISO format)")
    limit: int = Field(default=100, description="Maximum number of results", ge=1, le=500)


# ---------------------------------------------------------------------------
# FastMCP server + tools
# ---------------------------------------------------------------------------

mcp = FastMCP("maintenance-cmms-mcp")


@mcp.tool()
async def search_assets(query: str, limit: int = 10) -> str:
    """Search for assets by name or ID in the CMMS."""
    response = await _request_with_retry("GET", "/assets")
    all_assets: List[Dict] = response.json()
    q = query.lower()
    results = [
        a for a in all_assets
        if q in a.get("asset_name", "").lower() or q in a.get("asset_id", "").lower()
    ][:limit]
    return json.dumps({"results": results}, indent=2)


@mcp.tool()
async def get_asset_metadata(asset_id: str) -> str:
    """Get detailed metadata for an asset from the CMMS."""
    response = await _request_with_retry("GET", f"/assets/{asset_id}")
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_work_orders(
    asset_id: Optional[str] = None, unit: Optional[str] = None, site: Optional[str] = None,
    status: Optional[str] = None, work_order_type: Optional[str] = None,
    start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100,
) -> str:
    """Retrieve work orders with filtering and pagination from the CMMS."""
    args = GetWorkOrdersArgs(
        asset_id=asset_id, unit=unit, site=site, status=status, work_order_type=work_order_type,
        start_date=start_date, end_date=end_date, limit=limit,
    )
    params_dict = {k: v for k, v in args.model_dump().items() if v is not None}
    response = await _request_with_retry("GET", "/work-orders", params=params_dict)
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_maintenance_logs(
    asset_id: Optional[str] = None, unit: Optional[str] = None, site: Optional[str] = None,
    activity_type: Optional[str] = None, start_date: Optional[str] = None,
    end_date: Optional[str] = None, limit: int = 100,
) -> str:
    """Retrieve maintenance logs with filtering and pagination from the CMMS."""
    args = GetMaintenanceLogsArgs(
        asset_id=asset_id, unit=unit, site=site, activity_type=activity_type,
        start_date=start_date, end_date=end_date, limit=limit,
    )
    params_dict = {k: v for k, v in args.model_dump().items() if v is not None}
    response = await _request_with_retry("GET", "/maintenance-logs", params=params_dict)
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_asset_work_order_summary(asset_id: str, days: int = 90) -> str:
    """Get work order summary KPIs for an asset from the CMMS."""
    response = await _request_with_retry(
        "GET", f"/assets/{asset_id}/work-order-summary", params={"days": days}
    )
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_asset_maintenance_summary(asset_id: str, days: int = 90) -> str:
    """Get maintenance activity summary KPIs for an asset from the CMMS."""
    response = await _request_with_retry(
        "GET", f"/assets/{asset_id}/maintenance-summary", params={"days": days}
    )
    return json.dumps(response.json(), indent=2)


@mcp.tool()
async def get_spare_parts(asset_id: Optional[str] = None) -> str:
    """Retrieve spare parts inventory from the CMMS."""
    params_dict = {"asset_id": asset_id} if asset_id else {}
    response = await _request_with_retry("GET", "/spare-parts", params=params_dict)
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
    return JSONResponse({"status": "ok", "upstream_cmms": upstream})


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9001)
