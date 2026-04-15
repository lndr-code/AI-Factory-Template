from langgraph.graph import StateGraph, START, END

from orchestrator.state import OrchestratorState
from orchestrator.nodes.build_with_claude import build_with_claude
from orchestrator.nodes.report_done import report_done
from orchestrator.nodes.preflight_environment import preflight_environment
from orchestrator.nodes.fallback_build_with_codex import fallback_build_with_codex
from orchestrator.nodes.review_and_commit import review_and_commit


def route_after_preflight(state: OrchestratorState) -> str:
    if state.get("builder_status") == "failed":
        return "report_done"
    return "build_with_claude"


def route_after_claude(state: OrchestratorState) -> str:
    if state.get("builder_status") == "success":
        return "review_and_commit"
    return "fallback_build_with_codex"


def route_after_codex(state: OrchestratorState) -> str:
    if state.get("builder_status") == "success":
        return "review_and_commit"
    return "report_done"


def create_graph():
    graph = StateGraph(OrchestratorState)

    graph.add_node("preflight_environment", preflight_environment)
    graph.add_node("build_with_claude", build_with_claude)
    graph.add_node("fallback_build_with_codex", fallback_build_with_codex)
    graph.add_node("review_and_commit", review_and_commit)
    graph.add_node("report_done", report_done)

    graph.add_edge(START, "preflight_environment")

    graph.add_conditional_edges(
        "preflight_environment",
        route_after_preflight,
        {
            "build_with_claude": "build_with_claude",
            "report_done": "report_done"
        }
    )

    graph.add_conditional_edges(
        "build_with_claude",
        route_after_claude,
        {
            "review_and_commit": "review_and_commit",
            "fallback_build_with_codex": "fallback_build_with_codex"
        }
    )

    graph.add_conditional_edges(
        "fallback_build_with_codex",
        route_after_codex,
        {
            "review_and_commit": "review_and_commit",
            "report_done": "report_done"
        }
    )

    graph.add_edge("review_and_commit", "report_done")
    graph.add_edge("report_done", END)

    return graph.compile()


app = create_graph()
