"""LangGraph workflow structure and failure-resilience tests."""

from agents import graph


def transactions() -> list[dict]:
    return [
        {"merchant": "Salary", "amount": 40000, "transaction_type": "credit", "category": "Transfers", "transaction_date": "2024-01-01"},
        {"merchant": "Swiggy", "amount": -500, "transaction_type": "debit", "category": "Food & Dining", "transaction_date": "2024-01-02"},
    ]


def test_compiled_graph_has_documented_nodes() -> None:
    workflow = graph.build_langgraph_workflow()
    assert workflow is not None
    node_names = set(workflow.get_graph().nodes)
    assert {
        "validate_node",
        "analytics_node",
        "leak_node",
        "subscription_node",
        "duplicate_node",
        "recommendation_node",
        "ai_enhance_node",
        "report_node",
    }.issubset(node_names)


def test_full_workflow_without_key_returns_rule_results(monkeypatch) -> None:
    monkeypatch.setattr(graph.settings, "ANTHROPIC_API_KEY", "")
    result = graph.run_agent_workflow({"transactions": transactions(), "warnings": [], "errors": []})
    assert result["current_step"] == "completed"
    assert result["ai_enhanced"] is False
    assert result["diagnosis"]
    assert isinstance(result["recommendations"], list)
    assert result["output_summary"]["ai_enhanced"] is False


def test_arbitrary_node_failure_keeps_workflow_alive(monkeypatch) -> None:
    def broken_node(_state):
        raise KeyError("forced")

    monkeypatch.setattr(graph, "analytics_node", broken_node)
    result = graph.sequential_workflow({"transactions": transactions()})
    assert result["current_step"] == "completed"
    assert any("broken_node failed: KeyError" in error for error in result["errors"])
    assert "output_summary" in result


def test_empty_and_large_workflows_complete(monkeypatch) -> None:
    monkeypatch.setattr(graph.settings, "ANTHROPIC_API_KEY", "")
    empty = graph.sequential_workflow({"transactions": []})
    large = graph.sequential_workflow({"transactions": transactions() * 500})
    assert "No transactions found" in empty["warnings"]
    assert large["current_step"] == "completed"
