"""Optional LangGraph multi-agent workflow for MoneyLeak AI insights."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, TypedDict

import httpx

from config import get_settings
from services.dashboard_service import get_category_breakdown, get_daily_spend, get_needs_wants_waste, get_summary, get_top_merchants
from services.duplicate_detector import detect_duplicates
from services.leakage_detector import detect_needs_wants_waste_detail, detect_small_spend_leakage
from services.money_leak_score import calculate_score
from services.report_summary import classify_personality, generate_saving_priority
from services.subscription_detector import detect_subscriptions

logger = logging.getLogger(__name__)
settings = get_settings()


class AgentState(TypedDict, total=False):
    """Typed state schema for the MoneyLeak AI LangGraph workflow."""

    statement_id: str
    user_id: str
    transactions: list[Any]
    analytics: dict[str, Any]
    subscriptions: list[dict[str, Any]]
    duplicates: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    diagnosis: str
    warnings: list[str]
    errors: list[str]
    current_step: str
    ai_enhanced: bool
    output_summary: dict[str, Any]


NodeFunction = Callable[[AgentState], AgentState]


def ensure_state_defaults(state: AgentState) -> AgentState:
    """Return a mutable state containing all required workflow keys."""
    safe_state: AgentState = dict(state or {})
    safe_state.setdefault("statement_id", "")
    safe_state.setdefault("user_id", "")
    safe_state.setdefault("transactions", [])
    safe_state.setdefault("analytics", {})
    safe_state.setdefault("subscriptions", [])
    safe_state.setdefault("duplicates", [])
    safe_state.setdefault("recommendations", [])
    safe_state.setdefault("diagnosis", "")
    safe_state.setdefault("warnings", [])
    safe_state.setdefault("errors", [])
    safe_state.setdefault("current_step", "queued")
    safe_state.setdefault("ai_enhanced", False)
    safe_state.setdefault("output_summary", {})
    return safe_state


def append_warning(state: AgentState, message: str) -> None:
    """Append one deduplicated warning to workflow state."""
    warnings = list(state.get("warnings", []))
    if message not in warnings:
        warnings.append(message)
    state["warnings"] = warnings


def append_error(state: AgentState, message: str) -> None:
    """Append one deduplicated error to workflow state."""
    errors = list(state.get("errors", []))
    if message not in errors:
        errors.append(message)
    state["errors"] = errors


def merge_service_warnings(state: AgentState, result: dict[str, Any]) -> None:
    """Copy warnings from a service result into workflow state."""
    for warning in result.get("warnings", []) if isinstance(result, dict) else []:
        append_warning(state, str(warning))


def service_data(result: dict[str, Any], default: Any) -> Any:
    """Return data from a service result with a defensive default."""
    if not isinstance(result, dict):
        return default
    return result.get("data", default)


def validate_node(state: AgentState) -> AgentState:
    """Validate initial state and flag empty transaction sets without raising."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "validate"
    transactions = safe_state.get("transactions", [])
    if not isinstance(transactions, list) or len(transactions) == 0:
        append_warning(safe_state, "No transactions found")
    return safe_state


def analytics_node(state: AgentState) -> AgentState:
    """Run deterministic dashboard analytics and store them in workflow state."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "analytics"
    transactions = safe_state.get("transactions", [])
    try:
        summary = get_summary(transactions)
        category_breakdown = get_category_breakdown(transactions)
        top_merchants = get_top_merchants(transactions, limit=5)
        daily_spend = get_daily_spend(transactions)
        needs_wants_waste = get_needs_wants_waste(transactions)
        for result in [summary, category_breakdown, top_merchants, daily_spend, needs_wants_waste]:
            merge_service_warnings(safe_state, result)
        safe_state["analytics"] = {
            "summary": service_data(summary, {}),
            "category_breakdown": service_data(category_breakdown, []),
            "top_merchants": service_data(top_merchants, []),
            "daily_spend": service_data(daily_spend, []),
            "needs_wants_waste": service_data(needs_wants_waste, {}),
        }
    except (AttributeError, TypeError, ValueError) as exc:
        append_error(safe_state, f"analytics_node failed: {exc.__class__.__name__}")
    return safe_state


def leak_node(state: AgentState) -> AgentState:
    """Run deterministic money leak detectors and attach leak analytics."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "leakage"
    transactions = safe_state.get("transactions", [])
    try:
        small_spends = detect_small_spend_leakage(transactions)
        waste_detail = detect_needs_wants_waste_detail(transactions)
        merge_service_warnings(safe_state, small_spends)
        merge_service_warnings(safe_state, waste_detail)
        analytics = dict(safe_state.get("analytics", {}))
        analytics["small_spend_leakage"] = service_data(small_spends, {})
        analytics["waste_detail"] = service_data(waste_detail, {})
        safe_state["analytics"] = analytics
    except (AttributeError, TypeError, ValueError) as exc:
        append_error(safe_state, f"leak_node failed: {exc.__class__.__name__}")
    return safe_state


def subscription_node(state: AgentState) -> AgentState:
    """Detect recurring subscriptions and attach them to workflow state."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "subscriptions"
    try:
        result = detect_subscriptions(safe_state.get("transactions", []))
        merge_service_warnings(safe_state, result)
        safe_state["subscriptions"] = service_data(result, [])
    except (AttributeError, TypeError, ValueError) as exc:
        append_error(safe_state, f"subscription_node failed: {exc.__class__.__name__}")
    return safe_state


def duplicate_node(state: AgentState) -> AgentState:
    """Detect duplicate transactions and attach them to workflow state."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "duplicates"
    try:
        result = detect_duplicates(safe_state.get("transactions", []))
        merge_service_warnings(safe_state, result)
        safe_state["duplicates"] = service_data(result, [])
    except (AttributeError, TypeError, ValueError) as exc:
        append_error(safe_state, f"duplicate_node failed: {exc.__class__.__name__}")
    return safe_state


def recommendation_node(state: AgentState) -> AgentState:
    """Generate deterministic saving recommendations and money leak diagnosis."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "recommendations"
    transactions = safe_state.get("transactions", [])
    try:
        score = calculate_score(transactions, safe_state.get("subscriptions", []), safe_state.get("duplicates", []))
        priority = generate_saving_priority(transactions, safe_state.get("subscriptions", []), safe_state.get("duplicates", []))
        personality = classify_personality(transactions, {"data": safe_state.get("analytics", {}).get("category_breakdown", [])})
        for result in [score, priority, personality]:
            merge_service_warnings(safe_state, result)
        score_data = service_data(score, {})
        safe_state["recommendations"] = service_data(priority, [])
        safe_state["diagnosis"] = str(score_data.get("diagnosis") or "MoneyLeak AI generated a rule-based spending diagnosis.")
        analytics = dict(safe_state.get("analytics", {}))
        analytics["money_leak_score"] = score_data
        analytics["spending_personality"] = service_data(personality, {})
        safe_state["analytics"] = analytics
    except (AttributeError, TypeError, ValueError) as exc:
        append_error(safe_state, f"recommendation_node failed: {exc.__class__.__name__}")
    return safe_state


def build_ai_prompt(state: AgentState) -> str:
    """Build a compact prompt for optional AI enrichment."""
    summary = state.get("analytics", {}).get("summary", {})
    recommendations = state.get("recommendations", [])[:5]
    return (
        "You are MoneyLeak AI. Improve this budgeting diagnosis in concise JSON only with keys "
        "diagnosis and recommendations. Do not provide financial advice, only budgeting guidance. "
        f"Summary: {json.dumps(summary, default=str)}. "
        f"Rule recommendations: {json.dumps(recommendations, default=str)}."
    )


def call_anthropic_for_enrichment(prompt: str) -> dict[str, Any] | None:
    """Call Anthropic directly with httpx and return parsed JSON when possible."""
    api_key = str(settings.ANTHROPIC_API_KEY or "").strip()
    if api_key == "":
        return None
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_json = response.json()
        content_items = response_json.get("content", []) if isinstance(response_json, dict) else []
        raw_text = ""
        if content_items and isinstance(content_items[0], dict):
            raw_text = str(content_items[0].get("text") or "")
        if raw_text == "":
            return None
        return json.loads(raw_text)
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Anthropic enrichment failed: %s", exc.__class__.__name__)
        return None


def ai_enhance_node(state: AgentState) -> AgentState:
    """Optionally enrich diagnosis and recommendations with an LLM."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "ai_enhance"
    if str(settings.ANTHROPIC_API_KEY or "").strip() == "":
        safe_state["ai_enhanced"] = False
        append_warning(safe_state, "AI enhancement skipped because ANTHROPIC_API_KEY is not configured")
        return safe_state
    enrichment = call_anthropic_for_enrichment(build_ai_prompt(safe_state))
    if not enrichment:
        safe_state["ai_enhanced"] = False
        append_warning(safe_state, "AI enhancement failed; rule-based results returned")
        return safe_state
    safe_state["ai_enhanced"] = True
    diagnosis = str(enrichment.get("diagnosis") or "").strip() if isinstance(enrichment, dict) else ""
    recommendations = enrichment.get("recommendations") if isinstance(enrichment, dict) else None
    if diagnosis:
        safe_state["diagnosis"] = diagnosis
    if isinstance(recommendations, list) and recommendations:
        safe_state["recommendations"] = recommendations
    return safe_state


def report_node(state: AgentState) -> AgentState:
    """Assemble the final workflow output summary."""
    safe_state = ensure_state_defaults(state)
    safe_state["current_step"] = "completed"
    safe_state["output_summary"] = {
        "statement_id": safe_state.get("statement_id"),
        "analytics": safe_state.get("analytics", {}),
        "subscriptions": safe_state.get("subscriptions", []),
        "duplicates": safe_state.get("duplicates", []),
        "recommendations": safe_state.get("recommendations", []),
        "diagnosis": safe_state.get("diagnosis", ""),
        "ai_enhanced": bool(safe_state.get("ai_enhanced", False)),
        "warnings": safe_state.get("warnings", []),
        "errors": safe_state.get("errors", []),
    }
    return safe_state


def safe_execute_node(node: NodeFunction, state: AgentState) -> AgentState:
    """Execute one node and preserve partial state if the node unexpectedly fails."""
    safe_state = ensure_state_defaults(state)
    try:
        return ensure_state_defaults(node(safe_state))
    except Exception as exc:
        logger.warning("Agent node failed: %s", exc.__class__.__name__)
        append_error(safe_state, f"{getattr(node, '__name__', 'node')} failed: {exc.__class__.__name__}")
        return safe_state


def sequential_workflow(state: AgentState) -> AgentState:
    """Run the workflow sequentially without requiring LangGraph runtime support."""
    safe_state = ensure_state_defaults(state)
    for node in [
        validate_node,
        analytics_node,
        leak_node,
        subscription_node,
        duplicate_node,
        recommendation_node,
        ai_enhance_node,
        report_node,
    ]:
        safe_state = safe_execute_node(node, safe_state)
    return safe_state


def build_langgraph_workflow() -> Any | None:
    """Build and compile the LangGraph StateGraph workflow when LangGraph is available."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        logger.warning("LangGraph is not installed; sequential agent workflow will be used")
        return None
    try:
        workflow = StateGraph(AgentState)
        workflow.add_node("validate_node", validate_node)
        workflow.add_node("analytics_node", analytics_node)
        workflow.add_node("leak_node", leak_node)
        workflow.add_node("subscription_node", subscription_node)
        workflow.add_node("duplicate_node", duplicate_node)
        workflow.add_node("recommendation_node", recommendation_node)
        workflow.add_node("ai_enhance_node", ai_enhance_node)
        workflow.add_node("report_node", report_node)
        workflow.set_entry_point("validate_node")
        workflow.add_edge("validate_node", "analytics_node")
        workflow.add_edge("analytics_node", "leak_node")
        workflow.add_edge("leak_node", "subscription_node")
        workflow.add_edge("subscription_node", "duplicate_node")
        workflow.add_edge("duplicate_node", "recommendation_node")
        workflow.add_edge("recommendation_node", "ai_enhance_node")
        workflow.add_edge("ai_enhance_node", "report_node")
        workflow.add_edge("report_node", END)
        return workflow.compile()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        logger.warning("LangGraph workflow could not be compiled: %s", exc.__class__.__name__)
        return None


def run_agent_workflow(initial_state: AgentState) -> AgentState:
    """Run the MoneyLeak AI workflow with LangGraph when possible, otherwise sequentially."""
    safe_state = ensure_state_defaults(initial_state)
    graph = build_langgraph_workflow()
    if graph is None:
        return sequential_workflow(safe_state)
    try:
        return ensure_state_defaults(graph.invoke(safe_state))
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        append_error(safe_state, f"langgraph invoke failed: {exc.__class__.__name__}")
        return sequential_workflow(safe_state)
