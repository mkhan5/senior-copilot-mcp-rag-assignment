import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import random

app = FastAPI(title="Maintenance CMMS API", version="1.0.0")

DB_PATH = os.getenv("CMMS_DB_PATH", "/data/maintenance.db")

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

WORK_ORDER_TYPES = ["preventive", "corrective", "predictive", "emergency"]
WORK_ORDER_STATUSES = ["open", "in_progress", "completed", "cancelled"]
PRIORITIES = ["low", "medium", "high", "critical"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            asset_name TEXT NOT NULL,
            unit TEXT,
            site TEXT,
            asset_type TEXT,
            criticality TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            unit TEXT,
            site TEXT,
            work_order_type TEXT,
            status TEXT,
            priority TEXT,
            description TEXT,
            created_date TEXT,
            scheduled_date TEXT,
            completed_date TEXT,
            assigned_to TEXT,
            cost REAL,
            FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            log_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            unit TEXT,
            site TEXT,
            activity_type TEXT,
            description TEXT,
            performed_date TEXT,
            performed_by TEXT,
            duration_hours REAL,
            cost REAL,
            parts_used TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spare_parts (
            part_id TEXT PRIMARY KEY,
            asset_id TEXT,
            part_name TEXT,
            part_number TEXT,
            quantity INTEGER,
            min_stock INTEGER,
            location TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets (asset_id)
        )
    """)

    # Insert assets if empty
    cursor.execute("SELECT COUNT(*) FROM assets")
    if cursor.fetchone()[0] == 0:
        for asset in ASSETS:
            cursor.execute("""
                INSERT INTO assets (asset_id, asset_name, unit, site, asset_type, criticality)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (asset["asset_id"], asset["asset_name"], asset["unit"], asset["site"], asset["asset_type"], asset["criticality"]))

    # Insert sample work orders if empty
    cursor.execute("SELECT COUNT(*) FROM work_orders")
    if cursor.fetchone()[0] == 0:
        random.seed(42)
        for i in range(100):
            asset = random.choice(ASSETS)
            created = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 180))
            scheduled = created + timedelta(days=random.randint(1, 30))
            completed = scheduled + timedelta(days=random.randint(-5, 10)) if random.random() > 0.2 else None
            wo_id = f"WO-{20260000 + i}"
            cursor.execute("""
                INSERT INTO work_orders (work_order_id, asset_id, asset_name, unit, site, work_order_type, status, priority, description, created_date, scheduled_date, completed_date, assigned_to, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wo_id, asset["asset_id"], asset["asset_name"], asset["unit"], asset["site"],
                random.choice(WORK_ORDER_TYPES),
                random.choice(WORK_ORDER_STATUSES) if not completed else "completed",
                random.choice(PRIORITIES),
                f"Maintenance work order for {asset['asset_name']}",
                created.isoformat(), scheduled.isoformat(), completed.isoformat() if completed else None,
                f"Technician-{random.randint(1, 10)}",
                round(random.uniform(500, 50000), 2)
            ))

    # Insert sample maintenance logs if empty
    cursor.execute("SELECT COUNT(*) FROM maintenance_logs")
    if cursor.fetchone()[0] == 0:
        for i in range(80):
            asset = random.choice(ASSETS)
            performed = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 180))
            log_id = f"LOG-{20260000 + i}"
            cursor.execute("""
                INSERT INTO maintenance_logs (log_id, asset_id, asset_name, unit, site, activity_type, description, performed_date, performed_by, duration_hours, cost, parts_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id, asset["asset_id"], asset["asset_name"], asset["unit"], asset["site"],
                random.choice(["inspection", "lubrication", "replacement", "calibration", "repair"]),
                f"Routine maintenance on {asset['asset_name']}",
                performed.isoformat(),
                f"Technician-{random.randint(1, 10)}",
                round(random.uniform(0.5, 8.0), 1),
                round(random.uniform(100, 10000), 2),
                json.dumps([f"Part-{random.randint(1, 20)}" for _ in range(random.randint(0, 3))])
            ))

    # Insert sample spare parts if empty
    cursor.execute("SELECT COUNT(*) FROM spare_parts")
    if cursor.fetchone()[0] == 0:
        for i, asset in enumerate(ASSETS):
            for j in range(random.randint(2, 5)):
                part_id = f"PART-{asset['asset_id']}-{j}"
                cursor.execute("""
                    INSERT INTO spare_parts (part_id, asset_id, part_name, part_number, quantity, min_stock, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    part_id, asset["asset_id"],
                    f"{asset['asset_type'].capitalize()} Part {j+1}",
                    f"PN-{asset['asset_id']}-{j+1:03d}",
                    random.randint(0, 10),
                    random.randint(1, 3),
                    f"Warehouse-{random.randint(1, 3)}"
                ))

    conn.commit()
    conn.close()


import json
init_db()


class Asset(BaseModel):
    asset_id: str
    asset_name: str
    unit: str
    site: str
    asset_type: str
    criticality: str


class WorkOrder(BaseModel):
    work_order_id: str
    asset_id: str
    asset_name: str
    unit: str
    site: str
    work_order_type: str
    status: str
    priority: str
    description: str
    created_date: str
    scheduled_date: str
    completed_date: Optional[str] = None
    assigned_to: str
    cost: float


class MaintenanceLog(BaseModel):
    log_id: str
    asset_id: str
    asset_name: str
    unit: str
    site: str
    activity_type: str
    description: str
    performed_date: str
    performed_by: str
    duration_hours: float
    cost: float
    parts_used: List[str]


class SparePart(BaseModel):
    part_id: str
    asset_id: Optional[str] = None
    part_name: str
    part_number: str
    quantity: int
    min_stock: int
    location: str


@app.get("/health")
def health():
    return {"status": "healthy", "service": "maintenance-cmms"}


@app.get("/assets", response_model=List[Asset])
def get_assets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)


@app.get("/work-orders", response_model=List[WorkOrder])
def get_work_orders(
    asset_id: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    site: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    work_order_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM work_orders WHERE 1=1"
    params = []
    if asset_id:
        query += " AND asset_id = ?"
        params.append(asset_id)
    if unit:
        query += " AND unit = ?"
        params.append(unit)
    if site:
        query += " AND site = ?"
        params.append(site)
    if status:
        query += " AND status = ?"
        params.append(status)
    if work_order_type:
        query += " AND work_order_type = ?"
        params.append(work_order_type)
    if start_date:
        query += " AND created_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND created_date <= ?"
        params.append(end_date)
    query += " ORDER BY created_date DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/work-orders/{work_order_id}", response_model=WorkOrder)
def get_work_order(work_order_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM work_orders WHERE work_order_id = ?", (work_order_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Work order not found")
    return dict(row)


@app.get("/maintenance-logs", response_model=List[MaintenanceLog])
def get_maintenance_logs(
    asset_id: Optional[str] = Query(None),
    unit: Optional[str] = Query(None),
    site: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM maintenance_logs WHERE 1=1"
    params = []
    if asset_id:
        query += " AND asset_id = ?"
        params.append(asset_id)
    if unit:
        query += " AND unit = ?"
        params.append(unit)
    if site:
        query += " AND site = ?"
        params.append(site)
    if activity_type:
        query += " AND activity_type = ?"
        params.append(activity_type)
    if start_date:
        query += " AND performed_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND performed_date <= ?"
        params.append(end_date)
    query += " ORDER BY performed_date DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["parts_used"] = json.loads(d["parts_used"]) if d["parts_used"] else []
        result.append(d)
    return result


@app.get("/maintenance-logs/{log_id}", response_model=MaintenanceLog)
def get_maintenance_log(log_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM maintenance_logs WHERE log_id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Maintenance log not found")
    d = dict(row)
    d["parts_used"] = json.loads(d["parts_used"]) if d["parts_used"] else []
    return d


@app.get("/spare-parts", response_model=List[SparePart])
def get_spare_parts(asset_id: Optional[str] = Query(None)):
    conn = get_db()
    cursor = conn.cursor()
    if asset_id:
        cursor.execute("SELECT * FROM spare_parts WHERE asset_id = ?", (asset_id,))
    else:
        cursor.execute("SELECT * FROM spare_parts")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/spare-parts/{part_id}", response_model=SparePart)
def get_spare_part(part_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM spare_parts WHERE part_id = ?", (part_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Spare part not found")
    return dict(row)


@app.get("/assets/{asset_id}/work-order-summary")
def get_asset_work_order_summary(asset_id: str, days: int = Query(90)):
    conn = get_db()
    cursor = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
            SUM(CASE WHEN status IN ('open', 'in_progress') THEN 1 ELSE 0 END) as open_orders,
            SUM(cost) as total_cost,
            AVG(cost) as avg_cost
        FROM work_orders
        WHERE asset_id = ? AND created_date >= ?
    """, (asset_id, since))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


@app.get("/assets/{asset_id}/maintenance-summary")
def get_asset_maintenance_summary(asset_id: str, days: int = Query(90)):
    conn = get_db()
    cursor = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("""
        SELECT 
            COUNT(*) as total_activities,
            SUM(duration_hours) as total_hours,
            SUM(cost) as total_cost,
            AVG(cost) as avg_cost
        FROM maintenance_logs
        WHERE asset_id = ? AND performed_date >= ?
    """, (asset_id, since))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)