"""End-to-end tests for the complete MCP + RAG workflow."""

import pytest
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../apps/backend'))

from main import (
    CopilotState,
    copilot_graph,
    alarm_mcp_client,
    maint_mcp_client,
    rag_client,
)


class TestCompleteMCPRAGWorkflow:
    """Complete end-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_mcp_rag_integration_scenario(self):
        """
        Test the mandatory acceptance scenario from the assignment:
        Investigate recurring high-severity alarms for Boiler Feed Pump 101 
        over the last 90 days, identify likely contributing factors, 
        retrieve the relevant operating procedure, and provide recommended 
        actions with source evidence.
        """
        initial_state = CopilotState(
            user_query=(
                "Investigate recurring high-severity alarms for Boiler Feed Pump 101 "
                "over the last 90 days, identify likely contributing factors, "
                "retrieve the relevant operating procedure, and provide recommended "
                "actions with source evidence."
            ),
            session_id="e2e-acceptance-test"
        )

        # Execute the complete workflow
        final_state = await copilot_graph.ainvoke(initial_state)

        # Handle both dict and object return types
        if isinstance(final_state, dict):
            alarm_results = final_state.get("alarm_mcp_results", [])
            maint_results = final_state.get("maint_mcp_results", [])
            rag_results = final_state.get("rag_results", [])
            citations = final_state.get("citations", [])
            mcp_trace = final_state.get("mcp_trace", [])
            final_answer = final_state.get("final_answer", "")
            query_plan = final_state.get("query_plan", [])
            confidence = final_state.get("confidence", 0.0)
        else:
            alarm_results = final_state.alarm_mcp_results
            maint_results = final_state.maint_mcp_results
            rag_results = final_state.rag_results
            citations = final_state.citations
            mcp_trace = final_state.mcp_trace
            final_answer = final_state.final_answer
            query_plan = final_state.query_plan
            confidence = final_state.confidence

        # 1. Asset resolution through MCP tool (search_assets)
        search_assets_calls = [r for r in alarm_results if r.get("tool") == "search_assets"]
        assert len(search_assets_calls) > 0, "Should have called search_assets for asset resolution"
        assert search_assets_calls[0]["result"]["results"][0]["asset_id"] == "BFP-101"

        # 2. Multi-step Alarm Management API chaining through MCP
        alarm_tools_called = {r["tool"] for r in alarm_results}
        assert "get_alarms" in alarm_tools_called, "Should have called get_alarms"
        assert "get_alarm_summary" in alarm_tools_called, "Should have called get_alarm_summary"
        # Multiple alarm tools = multi-step chaining

        # 3. Document retrieval through RAG
        assert len(rag_results) > 0, "Should have retrieved documents via RAG"
        assert len(citations) > 0, "Should have RAG citations"

        # 4. Combined reasoning - both MCP servers + RAG
        assert len(alarm_results) > 0, "Should have alarm data"
        assert len(maint_results) > 0, "Should have maintenance data"
        maint_tools_called = {r["tool"] for r in maint_results}
        assert "get_asset_work_order_summary" in maint_tools_called
        assert "get_asset_maintenance_summary" in maint_tools_called

        # 5. Citations present
        assert len(citations) > 0, "Should have source citations"

        # 6. GUI output - final answer with structure
        assert final_answer, "Should have final answer"
        assert len(final_answer) > 100, "Answer should be substantial"

        # 7. MCP execution trace - both servers
        alarm_traces = [t for t in mcp_trace if t.get("server") == "alarm-management"]
        maint_traces = [t for t in mcp_trace if t.get("server") == "maintenance-cmms"]
        assert len(alarm_traces) > 0, "Should have alarm-management trace"
        assert len(maint_traces) > 0, "Should have maintenance-cmms trace"

        # 8. Query plan visibility
        assert len(query_plan) > 0, "Should have query plan"

        # Confidence should be reasonable
        assert confidence > 0.0, "Should have confidence score"

    @pytest.mark.asyncio
    async def test_workflow_structure(self):
        """Verify the workflow graph has the correct structure."""
        # Get the compiled graph
        graph = copilot_graph.get_graph()
        nodes = graph.nodes

        # Required nodes
        required_nodes = [
            "detect_intent",
            "discover_mcp_tools",
            "plan_mcp_execution",
            "execute_alarm_tools",
            "execute_maintenance_tools",
            "query_rag",
            "synthesize_answer",
        ]
        for node in required_nodes:
            assert node in nodes, f"Missing required node: {node}"

        # Check edges for parallel execution
        # execute_alarm_tools should fan out to both execute_maintenance_tools and query_rag
        edges = graph.edges
        edge_pairs = [(e[0], e[1]) for e in edges]
        
        # Check parallel branches exist
        assert ("execute_alarm_tools", "execute_maintenance_tools") in edge_pairs
        assert ("execute_alarm_tools", "query_rag") in edge_pairs
        
        # Check join at synthesize_answer
        assert ("execute_maintenance_tools", "synthesize_answer") in edge_pairs
        assert ("query_rag", "synthesize_answer") in edge_pairs

    @pytest.mark.asyncio
    async def test_dual_mcp_server_independence(self):
        """Test that both MCP servers can operate independently."""
        # Connect to alarm server
        alarm_tools = await alarm_mcp_client.connect()
        assert len(alarm_tools) >= 7, "Alarm server should have at least 7 tools"
        alarm_tool_names = {t.name for t in alarm_tools}
        assert "search_assets" in alarm_tool_names
        assert "get_alarms" in alarm_tool_names
        assert "get_alarm_summary" in alarm_tool_names
        assert "get_alarm_correlation" in alarm_tool_names

        # Connect to maintenance server
        maint_tools = await maint_mcp_client.connect()
        assert len(maint_tools) >= 7, "Maintenance server should have at least 7 tools"
        maint_tool_names = {t.name for t in maint_tools}
        assert "search_assets" in maint_tool_names
        assert "get_work_orders" in maint_tool_names
        assert "get_maintenance_logs" in maint_tool_names
        assert "get_asset_work_order_summary" in maint_tool_names

        # Disconnect both
        await alarm_mcp_client.disconnect()
        await maint_mcp_client.disconnect()

    @pytest.mark.asyncio
    async def test_cross_server_asset_resolution(self):
        """Test that asset resolution works across both servers using same asset IDs."""
        # Connect both
        await alarm_mcp_client.connect()
        await maint_mcp_client.connect()

        # Search asset via alarm server
        alarm_search = await alarm_mcp_client.call_tool("search_assets", {"query": "Boiler Feed Pump 101", "limit": 5})
        assert "results" in alarm_search
        asset_id = alarm_search["results"][0]["asset_id"]
        assert asset_id == "BFP-101"

        # Use same asset_id for maintenance server
        maint_summary = await maint_mcp_client.call_tool("get_asset_work_order_summary", {"asset_id": asset_id, "days": 90})
        assert isinstance(maint_summary, dict)
        assert "total_orders" in maint_summary or "total_orders" == 0

        # Cleanup
        await alarm_mcp_client.disconnect()
        await maint_mcp_client.disconnect()

    @pytest.mark.asyncio
    async def test_rag_retrieval_grounded(self):
        """Test that RAG retrieval returns grounded results with citations."""
        query = "What maintenance procedure for boiler feed pump?"
        result = rag_client.query(query, asset_id="Boiler Feed Pump 101")

        assert "answer" in result
        assert "citations" in result
        assert "confidence" in result
        assert isinstance(result["citations"], list)
        assert 0 <= result["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_partial_failure_resilience(self):
        """Test that workflow handles partial failures gracefully."""
        state = CopilotState(
            user_query="Show data for nonexistent asset XYZ-999",
            session_id="failure-test",
            intent={
                "assets": ["XYZ-999"],
                "time_range_days": 30,
                "needs_alarms": True,
                "needs_maintenance": True,
                "needs_documents": True,
            }
        )

        # Should not crash even with no data
        final_state = await copilot_graph.ainvoke(state)

        if isinstance(final_state, dict):
            final_answer = final_state.get("final_answer", "")
            mcp_trace = final_state.get("mcp_trace", [])
        else:
            final_answer = final_state.final_answer
            mcp_trace = final_state.mcp_trace

        # Should still produce an answer (even if stating no data found)
        assert final_answer, "Should produce answer even with no data"
        # Should have trace showing what happened
        assert len(mcp_trace) > 0, "Should have trace even on failure"


class TestMCPToolContracts:
    """Test MCP tool contract quality."""

    @pytest.mark.asyncio
    async def test_alarm_tool_input_schemas(self):
        """Test alarm MCP tools have proper input schemas."""
        await alarm_mcp_client.connect()
        
        for tool in alarm_mcp_client.tools:
            schema = tool.inputSchema
            assert "type" in schema, f"Tool {tool.name} missing schema type"
            assert schema["type"] == "object", f"Tool {tool.name} schema should be object"
            assert "properties" in schema, f"Tool {tool.name} missing properties"
            
            # Each property should have type
            for prop_name, prop_schema in schema["properties"].items():
                assert "type" in prop_schema, f"Tool {tool.name} property {prop_name} missing type"
                assert "description" in prop_schema, f"Tool {tool.name} property {prop_name} missing description"
        
        await alarm_mcp_client.disconnect()

    @pytest.mark.asyncio
    async def test_maintenance_tool_input_schemas(self):
        """Test maintenance MCP tools have proper input schemas."""
        await maint_mcp_client.connect()
        
        for tool in maint_mcp_client.tools:
            schema = tool.inputSchema
            assert "type" in schema, f"Tool {tool.name} missing schema type"
            assert schema["type"] == "object", f"Tool {tool.name} schema should be object"
            assert "properties" in schema, f"Tool {tool.name} missing properties"
            
            for prop_name, prop_schema in schema["properties"].items():
                assert "type" in prop_schema, f"Tool {tool.name} property {prop_name} missing type"
                assert "description" in prop_schema, f"Tool {tool.name} property {prop_name} missing description"
        
        await maint_mcp_client.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])