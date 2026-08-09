"""Unit tests for Maintenance MCP Server tools."""

import json
import pytest
import tempfile
import os
import sqlite3
from datetime import datetime, timedelta

# Add the maintenance server to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

from mcp_servers.maintenance.server import (
    SearchAssetsArgs,
    GetAssetMetadataArgs,
    GetWorkOrdersArgs,
    GetMaintenanceLogsArgs,
    GetAssetWorkOrderSummaryArgs,
    GetAssetMaintenanceSummaryArgs,
    GetSparePartsArgs,
    TOOLS,
    execute_with_retry,
    get_db_connection,
    settings,
)
from mcp_servers.maintenance.config import Settings


class TestMaintenanceMCPToolSchemas:
    """Test that all tool schemas are properly defined."""

    def test_all_tools_have_required_fields(self):
        """Each tool should have name, description, and inputSchema."""
        for tool in TOOLS:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            # MCP Tool uses input_schema (snake_case)
            assert hasattr(tool, 'input_schema')
            assert tool.name
            assert tool.description
            assert tool.input_schema

    def test_tool_names_are_unique(self):
        """Tool names should be unique."""
        names = [tool.name for tool in TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_present(self):
        """All expected maintenance tools should be registered."""
        expected_tools = {
            'search_assets',
            'get_asset_metadata',
            'get_work_orders',
            'get_maintenance_logs',
            'get_asset_work_order_summary',
            'get_asset_maintenance_summary',
            'get_spare_parts',
        }
        actual_tools = {tool.name for tool in TOOLS}
        assert expected_tools.issubset(actual_tools)


class TestMaintenanceMCPInputValidation:
    """Test Pydantic input validation for each tool."""

    def test_search_assets_args_valid(self):
        args = SearchAssetsArgs(query="BFP-101", limit=10)
        assert args.query == "BFP-101"
        assert args.limit == 10

    def test_search_assets_args_defaults(self):
        args = SearchAssetsArgs(query="pump")
        assert args.query == "pump"
        assert args.limit == 10

    def test_search_assets_args_limit_bounds(self):
        with pytest.raises(ValueError):
            SearchAssetsArgs(query="test", limit=0)
        with pytest.raises(ValueError):
            SearchAssetsArgs(query="test", limit=101)

    def test_get_asset_metadata_args(self):
        args = GetAssetMetadataArgs(asset_id="BFP-101")
        assert args.asset_id == "BFP-101"

    def test_get_work_orders_args_all_optional(self):
        args = GetWorkOrdersArgs()
        assert args.asset_id is None
        assert args.limit == 100

    def test_get_work_orders_args_with_filters(self):
        args = GetWorkOrdersArgs(
            asset_id="BFP-101",
            status="completed",
            work_order_type="preventive",
            start_date="2026-01-01",
            end_date="2026-12-31",
            limit=50
        )
        assert args.asset_id == "BFP-101"
        assert args.status == "completed"
        assert args.limit == 50

    def test_get_maintenance_logs_args(self):
        args = GetMaintenanceLogsArgs(
            asset_id="COMP-201",
            activity_type="inspection",
            limit=25
        )
        assert args.asset_id == "COMP-201"
        assert args.activity_type == "inspection"
        assert args.limit == 25

    def test_get_asset_work_order_summary_args(self):
        args = GetAssetWorkOrderSummaryArgs(asset_id="BFP-101", days=30)
        assert args.asset_id == "BFP-101"
        assert args.days == 30

    def test_get_asset_work_order_summary_bounds(self):
        with pytest.raises(ValueError):
            GetAssetWorkOrderSummaryArgs(asset_id="BFP-101", days=0)
        with pytest.raises(ValueError):
            GetAssetWorkOrderSummaryArgs(asset_id="BFP-101", days=366)

    def test_get_spare_parts_args(self):
        args = GetSparePartsArgs(asset_id="MOTOR-301")
        assert args.asset_id == "MOTOR-301"

    def test_get_spare_parts_args_no_filter(self):
        args = GetSparePartsArgs()
        assert args.asset_id is None


class TestMaintenanceMCPDatabase:
    """Test database operations with a temporary database."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        # Initialize with schema
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                unit TEXT,
                site TEXT,
                asset_type TEXT,
                criticality TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE work_orders (
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
                cost REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE maintenance_logs (
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
                parts_used TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE spare_parts (
                part_id TEXT PRIMARY KEY,
                asset_id TEXT,
                part_name TEXT,
                part_number TEXT,
                quantity INTEGER,
                min_stock INTEGER,
                location TEXT
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO assets (asset_id, asset_name, unit, site, asset_type, criticality)
            VALUES ('BFP-101', 'Boiler Feed Pump 101', 'Unit 1', 'NorthPlant', 'pump', 'high')
        """)

        cursor.execute("""
            INSERT INTO work_orders (work_order_id, asset_id, asset_name, unit, site, work_order_type, status, priority, description, created_date, scheduled_date, completed_date, assigned_to, cost)
            VALUES ('WO-001', 'BFP-101', 'Boiler Feed Pump 101', 'Unit 1', 'NorthPlant', 'preventive', 'completed', 'high', 'Test WO', '2026-06-01T00:00:00', '2026-06-05T00:00:00', '2026-06-06T00:00:00', 'Tech-1', 5000.0)
        """)

        cursor.execute("""
            INSERT INTO maintenance_logs (log_id, asset_id, asset_name, unit, site, activity_type, description, performed_date, performed_by, duration_hours, cost, parts_used)
            VALUES ('LOG-001', 'BFP-101', 'Boiler Feed Pump 101', 'Unit 1', 'NorthPlant', 'inspection', 'Test inspection', '2026-06-10T00:00:00', 'Tech-1', 2.0, 1000.0, '["Part-1", "Part-2"]')
        """)

        cursor.execute("""
            INSERT INTO spare_parts (part_id, asset_id, part_name, part_number, quantity, min_stock, location)
            VALUES ('PART-001', 'BFP-101', 'Pump Seal', 'PN-BFP-001', 5, 2, 'Warehouse-1')
        """)

        conn.commit()
        conn.close()

        # Override settings for this test
        original_path = settings.cmms_db_path
        settings.cmms_db_path = db_path

        yield db_path

        # Cleanup
        settings.cmms_db_path = original_path
        os.unlink(db_path)

    def test_search_assets(self, temp_db):
        """Test search_assets tool logic."""
        results = execute_with_retry(
            "SELECT asset_id, asset_name, unit, site, asset_type, criticality FROM assets WHERE asset_id LIKE ? OR asset_name LIKE ? ORDER BY asset_id LIMIT ?",
            ("%BFP%", "%BFP%", 10)
        )
        assert len(results) == 1
        assert results[0]['asset_id'] == 'BFP-101'
        assert results[0]['asset_name'] == 'Boiler Feed Pump 101'

    def test_get_asset_metadata(self, temp_db):
        """Test get_asset_metadata tool logic."""
        results = execute_with_retry(
            "SELECT asset_id, asset_name, unit, site, asset_type, criticality FROM assets WHERE asset_id = ?",
            ("BFP-101",)
        )
        assert len(results) == 1
        assert results[0]['asset_id'] == 'BFP-101'

    def test_get_work_orders(self, temp_db):
        """Test get_work_orders tool logic."""
        results = execute_with_retry(
            "SELECT * FROM work_orders WHERE 1=1 AND asset_id = ? ORDER BY created_date DESC LIMIT ?",
            ("BFP-101", 100)
        )
        assert len(results) == 1
        assert results[0]['work_order_id'] == 'WO-001'
        assert results[0]['status'] == 'completed'

    def test_get_maintenance_logs(self, temp_db):
        """Test get_maintenance_logs tool logic."""
        results = execute_with_retry(
            "SELECT * FROM maintenance_logs WHERE 1=1 AND asset_id = ? ORDER BY performed_date DESC LIMIT ?",
            ("BFP-101", 100)
        )
        assert len(results) == 1
        assert results[0]['log_id'] == 'LOG-001'
        assert results[0]['activity_type'] == 'inspection'
        # parts_used should be parsed as JSON
        assert results[0]['parts_used'] == '["Part-1", "Part-2"]'

    def test_get_asset_work_order_summary(self, temp_db):
        """Test get_asset_work_order_summary tool logic."""
        since = (datetime.now() - timedelta(days=90)).isoformat()
        results = execute_with_retry(
            """
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                SUM(CASE WHEN status IN ('open', 'in_progress') THEN 1 ELSE 0 END) as open_orders,
                SUM(cost) as total_cost,
                AVG(cost) as avg_cost
            FROM work_orders
            WHERE asset_id = ? AND created_date >= ?
            """,
            ("BFP-101", since)
        )
        assert len(results) == 1
        assert results[0]['total_orders'] == 1
        assert results[0]['completed_orders'] == 1
        assert results[0]['total_cost'] == 5000.0

    def test_get_asset_maintenance_summary(self, temp_db):
        """Test get_asset_maintenance_summary tool logic."""
        since = (datetime.now() - timedelta(days=90)).isoformat()
        results = execute_with_retry(
            """
            SELECT 
                COUNT(*) as total_activities,
                SUM(duration_hours) as total_hours,
                SUM(cost) as total_cost,
                AVG(cost) as avg_cost
            FROM maintenance_logs
            WHERE asset_id = ? AND performed_date >= ?
            """,
            ("BFP-101", since)
        )
        assert len(results) == 1
        assert results[0]['total_activities'] == 1
        assert results[0]['total_hours'] == 2.0
        assert results[0]['total_cost'] == 1000.0

    def test_get_spare_parts(self, temp_db):
        """Test get_spare_parts tool logic."""
        results = execute_with_retry(
            "SELECT * FROM spare_parts WHERE asset_id = ?",
            ("BFP-101",)
        )
        assert len(results) == 1
        assert results[0]['part_id'] == 'PART-001'
        assert results[0]['part_name'] == 'Pump Seal'
        assert results[0]['quantity'] == 5


class TestMaintenanceMCPRetryLogic:
    """Test retry logic for database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        # Initialize with schema
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE assets (
                asset_id TEXT PRIMARY KEY,
                asset_name TEXT NOT NULL,
                unit TEXT,
                site TEXT,
                asset_type TEXT,
                criticality TEXT
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO assets (asset_id, asset_name, unit, site, asset_type, criticality)
            VALUES ('BFP-101', 'Boiler Feed Pump 101', 'Unit 1', 'NorthPlant', 'pump', 'high')
        """)

        conn.commit()
        conn.close()

        # Override settings for this test
        original_path = settings.cmms_db_path
        settings.cmms_db_path = db_path

        yield db_path

        # Cleanup
        settings.cmms_db_path = original_path
        os.unlink(db_path)

    def test_execute_with_retry_success(self, temp_db):
        """Test successful execution."""
        results = execute_with_retry(
            "SELECT asset_id FROM assets WHERE asset_id = ?",
            ("BFP-101",)
        )
        assert len(results) == 1

    def test_execute_with_retry_not_found(self, temp_db):
        """Test query returning no results."""
        results = execute_with_retry(
            "SELECT asset_id FROM assets WHERE asset_id = ?",
            ("NONEXISTENT",)
        )
        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])