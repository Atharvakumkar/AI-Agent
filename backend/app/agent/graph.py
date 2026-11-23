from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.prompts import INVESTIGATION_SYSTEM_PROMPT, SYNTHESIS_USER_PROMPT
from app.agent.schemas import InvestigationReport
from app.agent.tools import IncidentProvider, create_diagnostic_tools
from app.anomalies.rules import DetectedAnomaly
from app.config import get_settings
from app.monitoring.collector import SystemMonitor


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    iteration_count: int
    max_iterations: int
    report: InvestigationReport | None


def route_after_investigate(state: AgentState) -> Literal["tools", "synthesize"]:
    """Route to ToolNode if the LLM requested tools and has budget left; otherwise synthesize."""
    last_message = state["messages"][-1]
    has_tool_calls = isinstance(last_message, AIMessage) and bool(last_message.tool_calls)

    if has_tool_calls and state["iteration_count"] < state["max_iterations"]:
        return "tools"
    return "synthesize"


class SentinelAgent:
    """Single-agent LangGraph investigator backed by Groq and read-only diagnostic tools."""

    def __init__(
        self,
        monitor: SystemMonitor,
        incident_provider: IncidentProvider | None = None,
        max_iterations: int = 6,
    ) -> None:
        self.monitor = monitor
        self.max_iterations = max_iterations
        self.tools = create_diagnostic_tools(monitor, incident_provider=incident_provider)
        self._compiled_graph = None

    def _build_llm(self) -> ChatGroq:
        settings = get_settings()
        if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
            raise ValueError(
                "GROQ_API_KEY is missing or still set to the placeholder in backend/.env."
            )
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=0.0,
            max_retries=3,
        )

    def _get_graph(self):
        if self._compiled_graph is not None:
            return self._compiled_graph

        llm = self._build_llm()
        llm_with_tools = llm.bind_tools(self.tools)
        structured_llm = llm.with_structured_output(InvestigationReport)
        tool_node = ToolNode(self.tools)

        def investigate_node(state: AgentState) -> dict:
            response = llm_with_tools.invoke(state["messages"])
            return {
                "messages": [response],
                "iteration_count": state["iteration_count"] + 1,
            }

        def synthesize_node(state: AgentState) -> dict:
            executed_tools: list[str] = []
            evidence_blocks: list[str] = []

            for msg in state["messages"]:
                if isinstance(msg, ToolMessage) and msg.name:
                    executed_tools.append(msg.name)
                    evidence_blocks.append(f"[{msg.name}]: {msg.content}")

            trigger_text = state["messages"][1].content if len(state["messages"]) > 1 else ""
            evidence_text = "\n".join(evidence_blocks) or "No tool outputs collected."

            synthesis_messages = [
                SystemMessage(
                    content=(
                        "You are SentinelAI. Produce a strictly factual InvestigationReport "
                        "separating confirmed observations from suspected causes. "
                        "Only recommend allowlisted actions."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Trigger:\n{trigger_text}\n\n"
                        f"Collected Tool Evidence:\n{evidence_text}\n\n"
                        f"{SYNTHESIS_USER_PROMPT}"
                    )
                ),
            ]
            report: InvestigationReport = structured_llm.invoke(synthesis_messages)
            report.tools_used = executed_tools
            return {"report": report}

        workflow = StateGraph(AgentState)
        workflow.add_node("investigate", investigate_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("synthesize", synthesize_node)

        workflow.set_entry_point("investigate")
        workflow.add_conditional_edges(
            "investigate",
            route_after_investigate,
            {
                "tools": "tools",
                "synthesize": "synthesize",
            },
        )
        workflow.add_edge("tools", "investigate")
        workflow.add_edge("synthesize", END)

        self._compiled_graph = workflow.compile()
        return self._compiled_graph

    def investigate(self, trigger_description: str) -> InvestigationReport:
        """Run a full multi-step investigation and return a structured InvestigationReport."""
        graph = self._get_graph()
        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=INVESTIGATION_SYSTEM_PROMPT),
                HumanMessage(content=trigger_description),
            ],
            "iteration_count": 0,
            "max_iterations": self.max_iterations,
            "report": None,
        }
        final_state = graph.invoke(initial_state)
        report = final_state.get("report")
        if report is None:
            raise RuntimeError("Agent finished without generating an InvestigationReport.")
        return report

    def investigate_anomaly(self, anomaly: DetectedAnomaly) -> InvestigationReport:
        """Convenience wrapper that formats a DetectedAnomaly into an investigation prompt."""
        trigger = (
            f"An anomaly was detected at {anomaly.timestamp.isoformat()}.\n"
            f"- Category: {anomaly.category.value}\n"
            f"- Severity: {anomaly.severity.value}\n"
            f"- Metric: {anomaly.metric_name} = {anomaly.current_value} "
            f"(threshold: {anomaly.threshold_value})\n"
            f"- Details: {anomaly.message}\n"
        )
        if anomaly.process_pid is not None:
            trigger += (
                f"- Reported Process: {anomaly.process_name} "
                f"(PID {anomaly.process_pid}, protected={anomaly.is_protected_process})\n"
            )
        trigger += "\nInvestigate this issue using your diagnostic tools and produce a report."
        return self.investigate(trigger)