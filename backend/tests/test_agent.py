import json
import os
from langchain_core.messages import AIMessage

from app.agent.graph import route_after_investigate
from app.agent.tools import create_diagnostic_tools
from app.monitoring.collector import SystemMonitor


def test_all_seven_tools_are_registered():
    monitor = SystemMonitor()
    tools = create_diagnostic_tools(monitor)
    names = {t.name for t in tools}

    expected = {
        "get_cpu_metrics",
        "get_memory_metrics",
        "get_disk_metrics",
        "get_top_processes",
        "get_system_information",
        "get_process_details",
        "get_previous_incidents",
    }
    assert names == expected


def test_diagnostic_tools_return_valid_json():
    monitor = SystemMonitor()
    tools_by_name = {t.name: t for t in create_diagnostic_tools(monitor)}

    cpu_data = json.loads(tools_by_name["get_cpu_metrics"].invoke({}))
    assert "usage_percent" in cpu_data

    mem_data = json.loads(tools_by_name["get_memory_metrics"].invoke({}))
    assert "available_gb" in mem_data

    disk_data = json.loads(tools_by_name["get_disk_metrics"].invoke({}))
    assert "primary_mount" in disk_data

    proc_data = json.loads(tools_by_name["get_top_processes"].invoke({"limit": 3}))
    assert "top_cpu" in proc_data

    sys_data = json.loads(tools_by_name["get_system_information"].invoke({}))
    assert "hostname" in sys_data

    detail_data = json.loads(
        tools_by_name["get_process_details"].invoke({"pid": os.getpid()})
    )
    assert detail_data["pid"] == os.getpid()

    missing_data = json.loads(
        tools_by_name["get_process_details"].invoke({"pid": 9999999})
    )
    assert "error" in missing_data


def test_previous_incidents_tool_uses_injected_provider():
    monitor = SystemMonitor()
    sample_incidents = [{"id": 1, "category": "CPU", "severity": "CRITICAL"}]
    tools_by_name = {
        t.name: t
        for t in create_diagnostic_tools(
            monitor, incident_provider=lambda limit: sample_incidents[:limit]
        )
    }

    result = json.loads(tools_by_name["get_previous_incidents"].invoke({"limit": 5}))
    assert result["count"] == 1
    assert result["incidents"][0]["category"] == "CPU"


def test_graph_routing_respects_tool_calls_and_max_iterations():
    msg_with_tool = AIMessage(
        content="",
        tool_calls=[{"name": "get_cpu_metrics", "args": {}, "id": "call_1"}],
    )
    msg_without_tool = AIMessage(content="Investigation complete.")

    # Tool call with remaining budget -> route to tools
    assert (
        route_after_investigate(
            {
                "messages": [msg_with_tool],
                "iteration_count": 1,
                "max_iterations": 6,
                "report": None,
            }
        )
        == "tools"
    )

    # Tool call at max_iterations -> force synthesize
    assert (
        route_after_investigate(
            {
                "messages": [msg_with_tool],
                "iteration_count": 6,
                "max_iterations": 6,
                "report": None,
            }
        )
        == "synthesize"
    )

    # No tool calls -> route to synthesize
    assert (
        route_after_investigate(
            {
                "messages": [msg_without_tool],
                "iteration_count": 2,
                "max_iterations": 6,
                "report": None,
            }
        )
        == "synthesize"
    )