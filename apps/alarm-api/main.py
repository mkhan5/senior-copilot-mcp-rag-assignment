from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import random

app = FastAPI(title="Alarm Management API Simulator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH_TOKEN = "demo-token"
ASSETS = [
    {"asset_id": "BFP-101", "asset_name": "Boiler Feed Pump 101", "unit": "Unit 1", "site": "NorthPlant", "asset_type": "pump", "criticality": "high"},
    {"asset_id": "BFP-102", "asset_name": "Boiler Feed Pump 102", "unit": "Unit 1", "site": "NorthPlant", "asset_type": "pump", "criticality": "high"},
    {"asset_id": "COMP-201", "asset_name": "Compressor 201", "unit": "Unit 2", "site": "NorthPlant", "asset_type": "compressor", "criticality": "high"},
    {"asset_id": "COMP-202", "asset_name": "Compressor 202", "unit": "Unit 2", "site": "NorthPlant", "asset_type": "compressor", "criticality": "medium"},
    {"asset_id": "MOTOR-301", "asset_name": "Motor 301", "unit": "Unit 3", "site": "SouthPlant", "asset_type": "motor", "criticality": "medium"},
    {"asset_id": "MOTOR-302", "asset_name": "Motor 302", "unit": "Unit 3", "site": "SouthPlant", "asset_type": "motor", "criticality": "low"},
    {"asset_id": "PUMP-401", "asset_name": "Pump 401", "unit": "Unit 4", "site": "EastRefinery", "asset_type": "pump", "criticality": "high"},
    {"asset_id": "PUMP-402", "asset_name": "Pump 402", "unit": "Unit 5", "site": "EastRefinery", "asset_type": "pump", "criticality": "medium"},
]

ALARM_NAMES = [
    "High Pressure", "Low Pressure", "High Temperature", "Low Temperature",
    "High Vibration", "Low Flow", "High Flow", "Motor Overload",
    "Bearing Temperature High", "Seal Leak", "Coupling Misalignment"
]

SEVERITIES = ["low", "medium", "high", "critical"]
STATUSES = ["active", "acknowledged", "cleared"]

ALARMS = []
random.seed(42)
for i in range(200):
    asset = random.choice(ASSETS)
    start = datetime(2026, 5, 1) + timedelta(days=random.randint(0, 60), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    end = start + timedelta(minutes=random.randint(5, 480)) if random.random() > 0.3 else None
    severity = random.choices(SEVERITIES, weights=[0.3, 0.4, 0.2, 0.1])[0]
    status = "active" if end is None else random.choice(STATUSES)
    ALARMS.append({
        "alarm_id": f"ALM-{10000+i}",
        "asset_id": asset["asset_id"],
        "asset_name": asset["asset_name"],
        "unit": asset["unit"],
        "site": asset["site"],
        "alarm_name": random.choice(ALARM_NAMES),
        "severity": severity,
        "status": status,
        "start_time": start.isoformat() + "Z",
        "end_time": end.isoformat() + "Z" if end else None,
        "ack_time": (start + timedelta(minutes=random.randint(1, 30))).isoformat() + "Z" if random.random() > 0.2 else None,
        "value": round(random.uniform(50, 150), 2),
        "setpoint": 100.0,
    })

# for mocking multiple alarms for an asset which doesn't have work orders
multi_alarm_asset = {"asset_id": "PUMP-403", "asset_name": "Pump 403", "unit": "Unit 6", "site": "EastRefinery", "asset_type": "pump", "criticality": "medium"}
for i in range(201, 204):
    asset = multi_alarm_asset
    start = datetime(2026, 5, 1) + timedelta(days=random.randint(0, 60), hours=random.randint(0, 23), minutes=random.randint(0, 59))
    end = start + timedelta(minutes=random.randint(5, 480)) if random.random() > 0.3 else None
    severity = random.choices(SEVERITIES, weights=[0.3, 0.4, 0.2, 0.1])[0]
    status = "active" if end is None else random.choice(STATUSES)
    ALARMS.append({
        "alarm_id": f"ALM-{10000+i}",
        "asset_id": asset["asset_id"],
        "asset_name": asset["asset_name"],
        "unit": asset["unit"],
        "site": asset["site"],
        "alarm_name": random.choice(ALARM_NAMES),
        "severity": severity,
        "status": status,
        "start_time": start.isoformat() + "Z",
        "end_time": end.isoformat() + "Z" if end else None,
        "ack_time": (start + timedelta(minutes=random.randint(1, 30))).isoformat() + "Z" if random.random() > 0.2 else None,
        "value": round(random.uniform(50, 150), 2),
        "setpoint": 100.0,
    })
ASSETS.append(multi_alarm_asset)

class AssetSearchResult(BaseModel):
    asset_id: str
    asset_name: str
    unit: str
    site: str
    asset_type: str
    criticality: str

class AssetSearchResponse(BaseModel):
    results: List[AssetSearchResult]
    total: int

class AssetMetadata(BaseModel):
    asset_id: str
    asset_name: str
    unit: str
    site: str
    asset_type: str
    criticality: str
    manufacturer: str
    model: str
    serial_number: str
    install_date: str
    last_maintenance: str
    next_maintenance: str

class Alarm(BaseModel):
    alarm_id: str
    asset_id: str
    asset_name: str
    unit: str
    site: str
    alarm_name: str
    severity: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    ack_time: Optional[str] = None
    value: float
    setpoint: float

class AlarmResponse(BaseModel):
    data: List[Alarm]
    total: int
    page: int
    page_size: int

class AlarmSummaryRequest(BaseModel):
    asset_ids: Optional[List[str]] = None
    unit: Optional[str] = None
    site: Optional[str] = None
    time_range: Dict[str, str]
    severity: Optional[List[str]] = None
    group_by: List[str] = ["alarm_name"]
    kpis: List[str] = ["alarm_count", "recurring_rate", "avg_ack_delay"]

class AlarmSummaryItem(BaseModel):
    group: Dict[str, Any]
    alarm_count: int
    recurring_rate: Optional[float] = None
    avg_ack_delay: Optional[float] = None

class AlarmSummaryResponse(BaseModel):
    data: List[AlarmSummaryItem]
    time_range: Dict[str, str]

class AlarmTrendsRequest(BaseModel):
    asset_ids: Optional[List[str]] = None
    unit: Optional[str] = None
    site: Optional[str] = None
    time_range: Dict[str, str]
    bucket: str = "daily"
    metrics: List[str] = ["alarm_count", "avg_ack_delay"]

class AlarmTrendsResponse(BaseModel):
    data: List[Dict[str, Any]]
    bucket: str
    metrics: List[str]

class CorrelationRequest(BaseModel):
    asset_ids: List[str]
    time_range: Dict[str, str]
    correlation_method: str = "cooccurrence"
    lag_window_minutes: int = 15
    severity_threshold: str = "medium"
    min_support: int = 1

class CorrelationResponse(BaseModel):
    correlations: List[Dict[str, Any]]

class FloodAnalysisRequest(BaseModel):
    unit: str
    time_range: Dict[str, str]
    threshold_count: int = 10
    rolling_window_minutes: int = 10

class FloodAnalysisResponse(BaseModel):
    flood_windows: List[Dict[str, Any]]

class RationalizationRequest(BaseModel):
    asset_ids: Optional[List[str]] = None
    unit: Optional[str] = None
    site: Optional[str] = None
    time_range: Dict[str, str]
    recurrence_threshold: int = 5
    stale_minutes_threshold: int = 180

class RationalizationResponse(BaseModel):
    candidates: List[Dict[str, Any]]

class PriorityScoreRequest(BaseModel):
    alarm_id: str

class PriorityScoreResponse(BaseModel):
    alarm_id: str
    priority_score: float
    factors: Dict[str, float]

class RecommendationRequest(BaseModel):
    alarm_id: str
    include_related: bool = True
    include_asset_context: bool = True
    include_historical_pattern: bool = True

class RecommendationResponse(BaseModel):
    alarm_id: str
    recommendations: List[Dict[str, Any]]

class CalculationGenerateRequest(BaseModel):
    calculation_type: str
    filters: Dict[str, Any]

class CalculationGenerateResponse(BaseModel):
    calculation_id: str
    code: str

class CalculationExecuteRequest(BaseModel):
    calculation_id: str
    filters: Dict[str, Any]

class CalculationExecuteResponse(BaseModel):
    calculation_id: str
    result: Dict[str, Any]

class KPIDefinition(BaseModel):
    kpi_id: str
    name: str
    description: str
    formula: str
    unit: str

def verify_auth(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid or missing authorization")

def get_trace_headers(
    trace_id: Optional[str] = Header(None, alias="trace_id"),
    x_client_id: Optional[str] = Header(None, alias="x-client-id"),
    x_metadata_tag: Optional[str] = Header(None, alias="x-metadata-tag"),
):
    return {"trace_id": trace_id, "x_client_id": x_client_id, "x_metadata_tag": x_metadata_tag}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "alarm-api"}

@app.get("/assets/search", response_model=AssetSearchResponse)
def search_assets(query: str = Query(...), limit: int = Query(10, le=100), _: None = Depends(verify_auth)):
    results = [a for a in ASSETS if query.lower() in a["asset_name"].lower() or query.lower() in a["asset_id"].lower()]
    return {"results": results[:limit], "total": len(results)}

@app.get("/assets/{asset_id}/metadata", response_model=AssetMetadata)
def get_asset_metadata(asset_id: str, _: None = Depends(verify_auth)):
    asset = next((a for a in ASSETS if a["asset_id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {
        **asset,
        "manufacturer": "ABB",
        "model": f"Model-{asset_id}",
        "serial_number": f"SN-{asset_id}-{random.randint(1000,9999)}",
        "install_date": "2020-01-15",
        "last_maintenance": "2026-03-10",
        "next_maintenance": "2026-09-10",
    }

@app.get("/alarms", response_model=AlarmResponse)
def get_alarms(
    asset_id: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    site: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    alarm_name: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    sort_by: str = Query("start_time"),
    sort_order: str = Query("desc"),
    _: None = Depends(verify_auth),
):
    filtered = ALARMS
    if asset_id:
        filtered = [a for a in filtered if a["asset_id"] == asset_id]
    if unit:
        filtered = [a for a in filtered if a["unit"] == unit]
    if site:
        filtered = [a for a in filtered if a["site"] == site]
    if severity:
        filtered = [a for a in filtered if a["severity"] == severity]
    if status:
        filtered = [a for a in filtered if a["status"] == status]
    if alarm_name:
        filtered = [a for a in filtered if alarm_name.lower() in a["alarm_name"].lower()]
    if start_time:
        filtered = [a for a in filtered if a["start_time"] >= start_time]
    if end_time:
        filtered = [a for a in filtered if a["start_time"] <= end_time]

    reverse = sort_order == "desc"
    filtered.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    return {"data": filtered[start:end], "total": total, "page": page, "page_size": page_size}

@app.get("/alarms/{alarm_id}", response_model=Alarm)
def get_alarm_by_id(alarm_id: str, _: None = Depends(verify_auth)):
    alarm = next((a for a in ALARMS if a["alarm_id"] == alarm_id), None)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm

@app.post("/alarms/summary", response_model=AlarmSummaryResponse)
def alarm_summary(request: AlarmSummaryRequest, trace: dict = Depends(get_trace_headers), _: None = Depends(verify_auth)):
    filtered = ALARMS
    if request.asset_ids:
        filtered = [a for a in filtered if a["asset_id"] in request.asset_ids]
    if request.unit:
        filtered = [a for a in filtered if a["unit"] == request.unit]
    if request.site:
        filtered = [a for a in filtered if a["site"] == request.site]
    if request.severity:
        filtered = [a for a in filtered if a["severity"] in request.severity]
    start = request.time_range.get("start_time", "2026-05-01T00:00:00Z")
    end = request.time_range.get("end_time", "2026-07-01T00:00:00Z")
    filtered = [a for a in filtered if start <= a["start_time"] <= end]

    groups: Dict[str, List[Dict]] = {}
    for alarm in filtered:
        key_parts = []
        for g in request.group_by:
            key_parts.append(str(alarm.get(g, "unknown")))
        key = "|".join(key_parts)
        groups.setdefault(key, []).append(alarm)

    data = []
    for key, alarms in groups.items():
        group_dict = {}
        for i, g in enumerate(request.group_by):
            group_dict[g] = alarms[0].get(g, "unknown")
        item = {"group": group_dict, "alarm_count": len(alarms)}
        if "recurring_rate" in request.kpis:
            unique_names = set(a["alarm_name"] for a in alarms)
            item["recurring_rate"] = round(len(alarms) / max(len(unique_names), 1), 2)
        if "avg_ack_delay" in request.kpis:
            ack_delays = []
            for a in alarms:
                if a.get("ack_time") and a.get("start_time"):
                    start_dt = datetime.fromisoformat(a["start_time"].replace("Z", "+00:00"))
                    ack_dt = datetime.fromisoformat(a["ack_time"].replace("Z", "+00:00"))
                    ack_delays.append((ack_dt - start_dt).total_seconds() / 60)
            item["avg_ack_delay"] = round(sum(ack_delays) / len(ack_delays), 1) if ack_delays else 0
        data.append(item)

    return {"data": data, "time_range": request.time_range}

@app.post("/alarms/trends", response_model=AlarmTrendsResponse)
def alarm_trends(request: AlarmTrendsRequest, _: None = Depends(verify_auth)):
    filtered = ALARMS
    if request.asset_ids:
        filtered = [a for a in filtered if a["asset_id"] in request.asset_ids]
    if request.unit:
        filtered = [a for a in filtered if a["unit"] == request.unit]
    if request.site:
        filtered = [a for a in filtered if a["site"] == request.site]
    start = request.time_range.get("start_time", "2026-05-01T00:00:00Z")
    end = request.time_range.get("end_time", "2026-07-01T00:00:00Z")
    filtered = [a for a in filtered if start <= a["start_time"] <= end]

    buckets: Dict[str, List[Dict]] = {}
    for alarm in filtered:
        dt = datetime.fromisoformat(alarm["start_time"].replace("Z", "+00:00"))
        if request.bucket == "daily":
            bucket_key = dt.strftime("%Y-%m-%d")
        elif request.bucket == "hourly":
            bucket_key = dt.strftime("%Y-%m-%d %H:00")
        else:
            bucket_key = dt.strftime("%Y-%m-%d")
        buckets.setdefault(bucket_key, []).append(alarm)

    data = []
    for bucket_key, alarms in sorted(buckets.items()):
        item = {"bucket": bucket_key}
        if "alarm_count" in request.metrics:
            item["alarm_count"] = len(alarms)
        if "avg_ack_delay" in request.metrics:
            ack_delays = []
            for a in alarms:
                if a.get("ack_time"):
                    start_dt = datetime.fromisoformat(a["start_time"].replace("Z", "+00:00"))
                    ack_dt = datetime.fromisoformat(a["ack_time"].replace("Z", "+00:00"))
                    ack_delays.append((ack_dt - start_dt).total_seconds() / 60)
            item["avg_ack_delay"] = round(sum(ack_delays) / len(ack_delays), 1) if ack_delays else 0
        data.append(item)

    return {"data": data, "bucket": request.bucket, "metrics": request.metrics}

@app.post("/alarms/correlation", response_model=CorrelationResponse)
def alarm_correlation(request: CorrelationRequest, trace: dict = Depends(get_trace_headers), _: None = Depends(verify_auth)):
    filtered = [a for a in ALARMS if a["asset_id"] in request.asset_ids]
    start = request.time_range.get("start_time", "2026-05-01T00:00:00Z")
    end = request.time_range.get("end_time", "2026-07-01T00:00:00Z")
    filtered = [a for a in filtered if start <= a["start_time"] <= end]
    if request.severity_threshold != "low":
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_sev = severity_order[request.severity_threshold]
        filtered = [a for a in filtered if severity_order[a["severity"]] >= min_sev]

    asset_alarms: Dict[str, List[Dict]] = {}
    for a in filtered:
        asset_alarms.setdefault(a["asset_id"], []).append(a)

    correlations = []
    asset_ids = list(asset_alarms.keys())
    for i, aid1 in enumerate(asset_ids):
        for aid2 in asset_ids[i+1:]:
            alarms1 = asset_alarms[aid1]
            alarms2 = asset_alarms[aid2]
            cooccur = 0
            for a1 in alarms1:
                t1 = datetime.fromisoformat(a1["start_time"].replace("Z", "+00:00"))
                for a2 in alarms2:
                    t2 = datetime.fromisoformat(a2["start_time"].replace("Z", "+00:00"))
                    if abs((t1 - t2).total_seconds()) <= request.lag_window_minutes * 60:
                        cooccur += 1
                        break
            if cooccur >= request.min_support:
                correlations.append({
                    "asset_id_1": aid1,
                    "asset_id_2": aid2,
                    "cooccurrence_count": cooccur,
                    "support": cooccur / max(len(alarms1), 1),
                })

    return {"correlations": correlations}

@app.post("/alarms/flood-analysis", response_model=FloodAnalysisResponse)
def flood_analysis(request: FloodAnalysisRequest, _: None = Depends(verify_auth)):
    filtered = [a for a in ALARMS if a["unit"] == request.unit]
    start = request.time_range.get("start_time", "2026-05-01T00:00:00Z")
    end = request.time_range.get("end_time", "2026-07-01T00:00:00Z")
    filtered = [a for a in filtered if start <= a["start_time"] <= end]
    filtered.sort(key=lambda x: x["start_time"])

    flood_windows = []
    window_minutes = request.rolling_window_minutes
    for i, alarm in enumerate(filtered):
        t_start = datetime.fromisoformat(alarm["start_time"].replace("Z", "+00:00"))
        t_end = t_start + timedelta(minutes=window_minutes)
        window_alarms = [a for a in filtered if datetime.fromisoformat(a["start_time"].replace("Z", "+00:00")) < t_end and datetime.fromisoformat(a["start_time"].replace("Z", "+00:00")) >= t_start]
        if len(window_alarms) >= request.threshold_count:
            flood_windows.append({
                "start": window_alarms[0]["start_time"],
                "end": window_alarms[-1]["start_time"],
                "alarm_count": len(window_alarms),
                "assets": list(set(a["asset_id"] for a in window_alarms)),
            })

    return {"flood_windows": flood_windows}

@app.post("/alarms/rationalization-candidates", response_model=RationalizationResponse)
def rationalization_candidates(request: RationalizationRequest, _: None = Depends(verify_auth)):
    filtered = ALARMS
    if request.asset_ids:
        filtered = [a for a in filtered if a["asset_id"] in request.asset_ids]
    if request.unit:
        filtered = [a for a in filtered if a["unit"] == request.unit]
    if request.site:
        filtered = [a for a in filtered if a["site"] == request.site]
    start = request.time_range.get("start_time", "2026-05-01T00:00:00Z")
    end = request.time_range.get("end_time", "2026-07-01T00:00:00Z")
    filtered = [a for a in filtered if start <= a["start_time"] <= end]

    alarm_groups: Dict[str, List[Dict]] = {}
    for a in filtered:
        key = f"{a['asset_id']}|{a['alarm_name']}"
        alarm_groups.setdefault(key, []).append(a)

    candidates = []
    for key, alarms in alarm_groups.items():
        asset_id, alarm_name = key.split("|", 1)
        if len(alarms) >= request.recurrence_threshold:
            latest = max(alarms, key=lambda x: x["start_time"])
            latest_time = datetime.fromisoformat(latest["start_time"].replace("Z", "+00:00"))
            stale_minutes = (datetime.now() - latest_time).total_seconds() / 60
            if stale_minutes >= request.stale_minutes_threshold:
                candidates.append({
                    "asset_id": asset_id,
                    "asset_name": alarms[0]["asset_name"],
                    "alarm_name": alarm_name,
                    "recurrence_count": len(alarms),
                    "last_occurrence": latest["start_time"],
                    "stale_minutes": round(stale_minutes),
                    "severity": max(alarms, key=lambda x: {"low":0,"medium":1,"high":2,"critical":3}[x["severity"]])["severity"],
                })

    return {"candidates": candidates}

@app.post("/alarms/priority-score", response_model=PriorityScoreResponse)
def priority_score(request: PriorityScoreRequest, _: None = Depends(verify_auth)):
    alarm = next((a for a in ALARMS if a["alarm_id"] == request.alarm_id), None)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    severity_weights = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    sev_score = severity_weights.get(alarm["severity"], 1) * 20
    freq_score = min(random.randint(10, 30), 30)
    impact_score = random.randint(10, 25)
    urgency_score = random.randint(5, 20)

    total = sev_score + freq_score + impact_score + urgency_score
    return {
        "alarm_id": request.alarm_id,
        "priority_score": round(total, 1),
        "factors": {
            "severity": sev_score,
            "frequency": freq_score,
            "impact": impact_score,
            "urgency": urgency_score,
        }
    }

@app.post("/recommendations/operator-actions", response_model=RecommendationResponse)
def operator_recommendations(request: RecommendationRequest, trace: dict = Depends(get_trace_headers), _: None = Depends(verify_auth)):
    alarm = next((a for a in ALARMS if a["alarm_id"] == request.alarm_id), None)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    base_recs = [
        {"action": "Verify alarm validity", "priority": "immediate", "category": "verification"},
        {"action": "Check sensor reading", "priority": "immediate", "category": "diagnosis"},
        {"action": "Review recent maintenance", "priority": "high", "category": "context"},
    ]
    if alarm["severity"] in ["high", "critical"]:
        base_recs.append({"action": "Initiate emergency response procedure", "priority": "immediate", "category": "response"})
    if request.include_related:
        base_recs.append({"action": "Check correlated assets for similar alarms", "priority": "high", "category": "correlation"})
    if request.include_asset_context:
        base_recs.append({"action": "Review asset operating parameters", "priority": "medium", "category": "context"})
    if request.include_historical_pattern:
        base_recs.append({"action": "Compare with historical alarm patterns", "priority": "medium", "category": "analysis"})

    return {"alarm_id": request.alarm_id, "recommendations": base_recs}

@app.post("/calculation-code/generate", response_model=CalculationGenerateResponse)
def generate_calculation(request: CalculationGenerateRequest, _: None = Depends(verify_auth)):
    calc_id = f"CALC-{uuid.uuid4().hex[:8]}"
    code_templates = {
        "alarm_flood_index": f"def alarm_flood_index(alarms, window_minutes=10, threshold=10):\n    # Calculate alarm flood index for {request.filters}\n    pass",
        "critical_alarm_density": f"def critical_alarm_density(alarms, unit='{request.filters.get('unit', '')}'):\n    # Calculate critical alarm density\n    pass",
        "operator_response_efficiency": f"def operator_response_efficiency(alarms, site='{request.filters.get('site', '')}'):\n    # Calculate operator response efficiency\n    pass",
        "nuisance_alarm_score": f"def nuisance_alarm_score(alarms, unit='{request.filters.get('unit', '')}'):\n    # Calculate nuisance alarm score\n    pass",
    }
    code = code_templates.get(request.calculation_type, f"# Calculation for {request.calculation_type}\ndef calculate():\n    pass")
    return {"calculation_id": calc_id, "code": code}

@app.post("/calculation-code/execute", response_model=CalculationExecuteResponse)
def execute_calculation(request: CalculationExecuteRequest, trace: dict = Depends(get_trace_headers), _: None = Depends(verify_auth)):
    return {
        "calculation_id": request.calculation_id,
        "result": {"value": round(random.uniform(0.5, 5.0), 2), "unit": "index", "status": "completed"}
    }

@app.get("/analytics/kpi-definitions", response_model=List[KPIDefinition])
def kpi_definitions(_: None = Depends(verify_auth)):
    return [
        {"kpi_id": "alarm_count", "name": "Alarm Count", "description": "Total number of alarms", "formula": "COUNT(alarms)", "unit": "count"},
        {"kpi_id": "recurring_rate", "name": "Recurring Rate", "description": "Ratio of total alarms to unique alarm types", "formula": "COUNT(alarms) / COUNT(DISTINCT alarm_name)", "unit": "ratio"},
        {"kpi_id": "avg_ack_delay", "name": "Average Acknowledgment Delay", "description": "Mean time to acknowledge alarms", "formula": "AVG(ack_time - start_time)", "unit": "minutes"},
        {"kpi_id": "suppression_candidate_rate", "name": "Suppression Candidate Rate", "description": "Percentage of alarms that are suppression candidates", "formula": "COUNT(suppression_candidates) / COUNT(alarms) * 100", "unit": "percent"},
        {"kpi_id": "critical_count", "name": "Critical Alarm Count", "description": "Number of critical severity alarms", "formula": "COUNT(alarms WHERE severity='critical')", "unit": "count"},
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)