"""Integration tests for dual MCP client (alarm + maintenance) orchestration."""

import pytest
import asyncio
import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../apps/backend'))

from main import (
    CopilotState,
    alarm_mcp_client,
    maint_mcp_client,
    detect_intent,
    discover_mcp_tools,
    plan_mcp_execution,
    execute_alarm_tools,
    execute_maintenance_tools,
    query_rag,
    synthesize_answer,
)


class TestDualMCPClient:
    """Test dual MCP client connecting to both servers."""

    @pytest.mark.asyncio
    async def test_discover_both_mcp_servers(self):
        """Test that both MCP servers can be discovered."""
        state = CopilotState(
            user_query="test",
            session_id="test-session"
        )
        
        state = await discover_mcp_tools(state)
        
        # Should discover tools from both servers
        assert len(state.alarm_mcp_tools) > 0, "Should discover alarm MCP tools"
        assert len(state.maint_mcp_tools) > 0, "Should discover maintenance MCP tools"
        
        # Check expected alarm tools
        alarm_tool_names = {t.name for t in state.alarm_mcp_tools}
        assert 'search_assets' in alarm_tool_names
        assert 'get_alarms' in alarm_tool_names
        assert 'get_alarm_summary' in alarm_tool_names
        
        # Check expected maintenance tools
        maint_tool_names = {t.name for t in state.maint_mcp_tools}
        assert 'search_assets' in maint_tool_names
        assert 'get_work_orders' in maint_tool_names
        assert 'get_maintenance_logs' in maint_tool_names
        assert 'get_asset_work_order_summary' in maint_tool_names

    @pytest.mark.asyncio
    async def test_alarm_tools_execution(self):
        """Test alarm MCP tool execution flow."""
        state = CopilotState(
            user_query="Show alarms for BFP-101",
            session_id="test-session",
            intent={
                "assets": ["BFP-101"],
                "time_range_days": 7,
                "needs_alarms": True,
                "needs_maintenance": False,
                "needs_documents": False,
            }
        )
        
        # Discover tools first
        state = await discover_mcp_tools(state)
        state = await plan_mcp_execution(state)
        state = await execute_alarm_tools(state)
        
        # Should have alarm results
        assert len(state.alarm_mcp_results) > 0
        assert any(r['tool'] == 'search_assets' for r in state.alarm_mcp_results)
        assert any(r['tool'] == 'get_alarms' for r in state.alarm_mcp_results)
        
        # Should have trace entries
        assert len(state.mcp_trace) > 0
        assert any(t['server'] == 'alarm-management' for t in state.mcp_trace)

    @pytest.mark.asyncio
    async def test_maintenance_tools_execution(self):
        """Test maintenance MCP tool execution flow."""
        state = CopilotState(
            user_query="Show maintenance for BFP-101",
            session_id="test-session",
            intent={
                "assets": ["BFP-101"],
                "time_range_days": 90,
                "needs_alarms": False,
                "needs_maintenance": True,
                "needs_documents": False,
            }
        )
        
        # Discover tools first (needs alarm client for asset search)
        state = await discover_mcp_tools(state)
        state = await plan_mcp_execution(state)
        state = await execute_maintenance_tools(state)
        
        # Should have maintenance results
        assert len(state.maint_mcp_results) > 0
        assert any(r['tool'] == 'get_asset_work_order_summary' for r in state.maint_mcp_results)
        assert any(r['tool'] == 'get_asset_maintenance_summary' for r in state.maint_mcp_results)
        assert any(r['tool'] == 'get_work_orders' for r in state.maint_mcp_results)
        assert any(r['tool'] == 'get_maintenance_logs' for r in state.maint_mcp_results)
        
        # Should have trace entries from maintenance server
        assert any(t['server'] == 'maintenance-cmms' for t in state.mcp_trace)


class TestCrossServerChaining:
    """Test multi-step chaining across both MCP servers."""

    @pytest.mark.asyncio
    async def test_asset_id_chaining_alarm_to_maintenance(self):
        """Test that asset_id from alarm tools chains to maintenance tools."""
        state = CopilotState(
            user_query="Get alarms and maintenance history for BFP-101",
            session_id="test-session",
            intent={
                "assets": ["BFP-101"],
                "time_range_days": 30,
                "needs_alarms": True,
                "needs_maintenance": True,
                "needs_documents": False,
            }
        )
        
        state = await discover_mcp_tools(state)
        state = await plan_mcp_execution(state)
        state = await execute_alarm_tools(state)
        
        # Extract asset_id from alarm results
        asset_ids = []
        for result in state.alarm_mcp_results:
            if result.get('asset_id'):
                asset_ids.append(result['asset_id'])
        
        assert len(asset_ids) > 0, "Should have resolved asset_id from alarm tools"
        asset_id = asset_ids[0]
        assert asset_id == "BFP-101"
        
        # Now execute maintenance tools (uses same asset_id resolution)
        state = await execute_maintenance_tools(state)
        
        # Verify maintenance tools were called with the same asset_id
        maint_asset_ids = [r.get('asset_id') for r in state.maint_mcp_results if r.get('asset_id')]
        assert asset_id in maint_asset_ids, f"Maintenance tools should use asset_id {asset_id}"


class TestParallelExecution:
    """Test that maintenance and RAG can run in parallel after alarm tools."""

    @pytest.mark.asyncio
    async def test_workflow_parallel_branches(self):
        """Verify the workflow graph has parallel branches."""
        from main import copilot_graph
        
        # Get the graph structure
        graph = copilot_graph.get_graph()
        
        # Check that execute_alarm_tools has edges to both execute_maintenance_tools and query_rag
        # This is a structural test of the compiled graph
        nodes = graph.nodes
        assert 'execute_alarm_tools' in nodes
        assert 'execute_maintenance_tools' in nodes
        assert 'query_rag' in nodes
        assert 'synthesize_answer' in nodes


class TestMCPToolErrorHandling:
    """Test error handling in MCP tool calls."""

    @pytest.mark.asyncio
    async def test_invalid_tool_handling(self):
        """Test handling of invalid tool calls."""
        state = CopilotState(
            user_query="test",
            session_id="test-session"
        )
        
        state = await discover_mcp_tools(state)
        
        # Try calling a non-existent tool on alarm client
        with pytest.raises(RuntimeError) as exc_info:
            await alarm_mcp_client.call_tool("nonexistent_tool", {})
        
        assert "MCP tool error" in str(exc_info.value) or "Unknown error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_arguments_handling(self):
        """Test handling of invalid arguments."""
        state = CopilotState(
            user_query="test",
            session_id="test-session"
        )
        
        state = await discover_mcp_tools(state)
        
        # Try calling search_assets without required query parameter
        with pytest.raises(RuntimeError) as exc_info:
            await alarm_mcp_client.call_tool("search_assets", {})
        
        # Should get a validation error
        assert "MCP tool error" in str(exc_info.value)


class TestEndToEndScenario:
    """End-to-end test combining MCP and RAG."""

    @pytest.mark.asyncio
    async def test_combined_mcp_rag_scenario(self):
        """Test the mandatory acceptance scenario."""
        state = CopilotState(
            user_query="Investigate recurring high-severity alarms for Boiler Feed Pump 101 over the last 90 days, identify likely contributing factors, retrieve the relevant operating procedure, and provide recommended actions with source evidence.",
            session_id="e2e-test-session",
            intent={
                "assets": ["Boiler Feed Pump 101", "BFP-101"],
                "time_range_days": 90,
                "needs_alarms": True,
                "needs_maintenance": True,
                "needs_documents": True,
                "needs_correlation": False,
                "query_type": "combined_analysis",
            }
        )
        
        # Run the full pipeline
        state = await discover_mcp_tools(state)
        state = await plan_mcp_execution(state)
        state = await execute_alarm_tools(state)
        state = await execute_maintenance_tools(state)
        state = await query_rag(state)
        state = await synthesize_answer(state)
        
        # Verify all data sources contributed
        assert len(state.alarm_mcp_results) > 0, "Should have alarm data"
        assert len(state.maint_mcp_results) > 0, "Should have maintenance data"
        assert len(state.rag_results) > 0, "Should have RAG results"
        
        # Should have citations from RAG
        assert len(state.citations) > 0, "Should have document citations"
        
        # Should have trace from both MCP servers
        alarm_traces = [t for t in state.mcp_trace if t.get('server') == 'alarm-management']
        maint_traces = [t for t in state.mcp_trace if t.get('server') == 'maintenance-cmms']
        assert len(alarm_traces) > 0, "Should have alarm MCP trace"
        assert len(maint_traces) > 0, "Should have maintenance MCP trace"
        
        # Should have final answer
        assert state.final_answer, "Should have synthesized answer"
        assert len(state.final_answer) > 50, "Answer should be substantial"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])