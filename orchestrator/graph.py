from langgraph.graph import StateGraph, START, END

from orchestrator.state import OrchestratorState
from orchestrator.nodes.check_tasks_exist import check_tasks_exist
from orchestrator.nodes.architect_agent import architect_agent
from orchestrator.nodes.critic_agent import critic_agent
from orchestrator.nodes.architect_refine import architect_refine
from orchestrator.nodes.preflight_environment import preflight_environment
from orchestrator.nodes.build_with_claude import build_with_claude
from orchestrator.nodes.fallback_build_with_codex import fallback_build_with_codex
from orchestrator.nodes.review_with_gemini import review_with_gemini
from orchestrator.nodes.review_and_commit import review_and_commit
from orchestrator.nodes.report_done import report_done


# ---------------------------------------------------------------------------
# Routing functions
# All routers are pure functions — they read state but never mutate it.
# ---------------------------------------------------------------------------

def route_after_start(state: OrchestratorState) -> str:
    """Route to architect phase if no tasks exist, otherwise go straight to build phase."""
    if state.get("task_status") == "no_tasks" or state.get("builder_status") == "no_tasks":
        return "architect_agent"
    return "preflight_environment"


def route_after_initial_architect(state: OrchestratorState) -> str:
    """After initial architecture generation: proceed to Critic or abort."""
    if state.get("planning_status") in {"failed", "awaiting_input"} or state.get("builder_status") == "failed":
        return "report_done"
    return "critic_agent"


def route_after_critic(state: OrchestratorState) -> str:
    """After Critic review: proceed to Architect Refinement or abort."""
    if state.get("critic_status") == "failed" or state.get("builder_status") == "failed":
        return "report_done"
    return "architect_refine"


def route_after_architect_refine(state: OrchestratorState) -> str:
    """
    After Architect Refinement: always exit to report_done.
    The outer loop in run_graph.py picks up the newly created tasks on the next iteration.
    Routing to preflight here with an empty current_task_file would be incorrect.
    """
    return "report_done"


def route_after_preflight(state: OrchestratorState) -> str:
    if state.get("preflight_status") == "failed" or state.get("builder_status") == "failed":
        return "report_done"
    return "build_with_claude"


def route_after_claude(state: OrchestratorState) -> str:
    if state.get("builder_status") == "policy_violation":
        return "report_done"
    if state.get("build_status") == "success" or state.get("builder_status") == "success":
        return "review_with_gemini"
    return "fallback_build_with_codex"


def route_after_codex(state: OrchestratorState) -> str:
    if state.get("build_status") == "success" or state.get("builder_status") == "success":
        return "review_with_gemini"
    return "report_done"


def route_after_review(state: OrchestratorState) -> str:
    """
    Route after Gemini review.
    Fix A: no state mutation here — report_done.py detects max-retry from state fields.
    """
    status = state.get("review_with_gemini_status")
    if status == "approved":
        return "review_and_commit"
    elif status == "needs_revision":
        retry_count = state.get("review_retry_count", state.get("retry_count", 0))
        max_retries = state.get("max_review_retries", state.get("max_retries", 2))
        if retry_count <= max_retries:
            return "build_with_claude"
        return "report_done"
    return "report_done"


def route_after_commit_or_validation(state: OrchestratorState) -> str:
    if state.get("review_status") == "needs_revision":
        retry_count = state.get("validation_retry_count", 0)
        max_retries = state.get("max_validation_retries", state.get("max_retries", 2))
        if retry_count <= max_retries:
            return "build_with_claude"
    return "report_done"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_graph():
    graph = StateGraph(OrchestratorState)

    # Register all nodes
    graph.add_node("check_tasks_exist", check_tasks_exist)
    graph.add_node("architect_agent", architect_agent)
    graph.add_node("critic_agent", critic_agent)
    graph.add_node("architect_refine", architect_refine)
    graph.add_node("preflight_environment", preflight_environment)
    graph.add_node("build_with_claude", build_with_claude)
    graph.add_node("fallback_build_with_codex", fallback_build_with_codex)
    graph.add_node("review_with_gemini", review_with_gemini)
    graph.add_node("review_and_commit", review_and_commit)
    graph.add_node("report_done", report_done)

    # Entry point
    graph.add_edge(START, "check_tasks_exist")

    # check_tasks_exist → architect phase OR build phase
    graph.add_conditional_edges(
        "check_tasks_exist",
        route_after_start,
        {
            "architect_agent": "architect_agent",
            "preflight_environment": "preflight_environment",
        },
    )

    # Planning phase: architect → critic → refine → done
    graph.add_conditional_edges(
        "architect_agent",
        route_after_initial_architect,
        {
            "critic_agent": "critic_agent",
            "report_done": "report_done",
        },
    )
    graph.add_conditional_edges(
        "critic_agent",
        route_after_critic,
        {
            "architect_refine": "architect_refine",
            "report_done": "report_done",
        },
    )
    graph.add_conditional_edges(
        "architect_refine",
        route_after_architect_refine,
        {
            "report_done": "report_done",
        },
    )

    # Build phase: preflight → claude → [gemini review | codex fallback]
    graph.add_conditional_edges(
        "preflight_environment",
        route_after_preflight,
        {
            "build_with_claude": "build_with_claude",
            "report_done": "report_done",
        },
    )
    graph.add_conditional_edges(
        "build_with_claude",
        route_after_claude,
        {
            "review_with_gemini": "review_with_gemini",
            "fallback_build_with_codex": "fallback_build_with_codex",
        },
    )
    graph.add_conditional_edges(
        "fallback_build_with_codex",
        route_after_codex,
        {
            "review_with_gemini": "review_with_gemini",
            "report_done": "report_done",
        },
    )

    # Review phase: gemini review → commit | retry | done
    graph.add_conditional_edges(
        "review_with_gemini",
        route_after_review,
        {
            "review_and_commit": "review_and_commit",
            "build_with_claude": "build_with_claude",
            "report_done": "report_done",
        },
    )

    # Commit → done → END
    graph.add_conditional_edges(
        "review_and_commit",
        route_after_commit_or_validation,
        {
            "build_with_claude": "build_with_claude",
            "report_done": "report_done",
        },
    )
    graph.add_edge("report_done", END)

    return graph.compile()


app = create_graph()
