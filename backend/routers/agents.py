"""Agentic analysis API routes for MoneyLeak AI."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agents.graph import run_agent_workflow
from config import get_settings
from database import SessionLocal, get_db
from dependencies import get_current_user
from models import AgentRun, Transaction, User
from models.enums import AgentRunStatus
from routers.dashboard import database_error_response, fetch_transactions_for_statement, no_statement_payload
from schemas.common import error_response, success_response
from services.duplicate_detector import detect_duplicates
from services.report_summary import generate_saving_priority
from services.subscription_detector import detect_subscriptions
from rag.vector_store import search_memory

router = APIRouter(prefix="/api/agents", tags=["Agents"])
settings = get_settings()
logger = logging.getLogger("moneyleak-ai.agents")


class AnalyzeRequest(BaseModel):
    """Request body for starting a background agent workflow."""

    statement_id: UUID


class RecommendRequest(BaseModel):
    """Request body for agent recommendation generation."""

    statement_id: UUID
    context: str | None = Field(default=None)


def serialize_agent_run(run: AgentRun) -> dict[str, Any]:
    """Serialize an AgentRun for API responses."""
    output = run.output_summary or {}
    return {
        "run_id": str(run.id),
        "current_step": str(run.current_step or "queued"),
        "status": getattr(run.status, "value", str(run.status)),
        "output_summary": output if getattr(run.status, "value", str(run.status)) == AgentRunStatus.COMPLETED.value else None,
        "ai_enhanced": bool(output.get("ai_enhanced", False)) if isinstance(output, dict) else False,
        "warnings": output.get("warnings", []) if isinstance(output, dict) else [],
    }


def update_run_failure(db: Session, run: AgentRun, message: str) -> None:
    """Mark an agent run as failed while preserving a structured output summary."""
    run.status = AgentRunStatus.FAILED
    run.current_step = "failed"
    run.error_message = message
    run.completed_at = datetime.now(timezone.utc)
    run.output_summary = {
        "diagnosis": "Agent workflow failed before analysis completed.",
        "ai_enhanced": False,
        "warnings": [],
        "errors": [message],
    }
    db.commit()


def execute_agent_run(run_id: UUID, user_id: UUID, statement_id: UUID) -> None:
    """Execute a persisted agent run in a fresh database session."""
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == user_id).first()
        if run is None:
            return
        run.current_step = "loading_transactions"
        db.commit()
        transactions = (
            db.query(Transaction)
            .filter(Transaction.user_id == user_id, Transaction.statement_id == statement_id)
            .order_by(Transaction.transaction_date.asc(), Transaction.created_at.asc())
            .all()
        )
        state = run_agent_workflow(
            {
                "statement_id": str(statement_id),
                "user_id": str(user_id),
                "transactions": transactions,
                "warnings": [],
                "errors": [],
                "current_step": "queued",
                "ai_enhanced": False,
            }
        )
        output_summary = state.get("output_summary", {})
        if not output_summary:
            output_summary = {
                "diagnosis": state.get("diagnosis", ""),
                "analytics": state.get("analytics", {}),
                "subscriptions": state.get("subscriptions", []),
                "duplicates": state.get("duplicates", []),
                "recommendations": state.get("recommendations", []),
                "warnings": state.get("warnings", []),
                "errors": state.get("errors", []),
                "ai_enhanced": bool(state.get("ai_enhanced", False)),
            }
        run.current_step = str(state.get("current_step") or "completed")
        run.status = AgentRunStatus.COMPLETED
        run.output_summary = output_summary
        run.error_message = "; ".join(state.get("errors", [])) if state.get("errors") else None
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        existing_run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == user_id).first()
        if existing_run is not None:
            update_run_failure(db, existing_run, f"database_error:{exc.__class__.__name__}")
    except Exception as exc:
        db.rollback()
        logger.warning("Agent workflow failed: %s", exc.__class__.__name__)
        existing_run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == user_id).first()
        if existing_run is not None:
            update_run_failure(db, existing_run, f"workflow_error:{exc.__class__.__name__}")
    finally:
        db.close()


def build_rule_based_recommendations(transactions: list[Any]) -> dict[str, Any]:
    """Build deterministic recommendations from analytics services."""
    subscriptions_result = detect_subscriptions(transactions)
    duplicates_result = detect_duplicates(transactions)
    recommendations_result = generate_saving_priority(
        transactions,
        subscriptions_result.get("data", []),
        duplicates_result.get("data", []),
    )
    warnings = list(
        dict.fromkeys(
            subscriptions_result.get("warnings", [])
            + duplicates_result.get("warnings", [])
            + recommendations_result.get("warnings", [])
        )
    )
    return {"recommendations": recommendations_result.get("data", []), "warnings": warnings}


def optional_ai_recommendations(rule_based: dict[str, Any], memories: list[str], context: str | None) -> dict[str, Any]:
    """Return AI recommendations when configured, otherwise return rule-based output."""
    if str(settings.ANTHROPIC_API_KEY or "").strip() == "":
        return {
            "recommendations": rule_based.get("recommendations", []),
            "ai_enhanced": False,
            "reason": "api_key_not_configured",
            "memory_context": memories,
        }
    from agents.graph import call_anthropic_for_enrichment

    prompt = (
        "Return JSON only with key recommendations. Improve these budgeting recommendations using memory context. "
        f"Recommendations: {rule_based.get('recommendations', [])}. "
        f"Memories: {memories}. Extra context: {context or ''}."
    )
    enrichment = call_anthropic_for_enrichment(prompt)
    if isinstance(enrichment, dict) and isinstance(enrichment.get("recommendations"), list):
        return {
            "recommendations": enrichment.get("recommendations", []),
            "ai_enhanced": True,
            "reason": "ai_enriched",
            "memory_context": memories,
        }
    return {
        "recommendations": rule_based.get("recommendations", []),
        "ai_enhanced": False,
        "reason": "ai_enrichment_failed",
        "memory_context": memories,
    }


@router.post("/analyze", response_model=None)
def analyze_statement(
    payload: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Start a background LangGraph analysis workflow for a statement."""
    try:
        statement, _transactions = fetch_transactions_for_statement(db, current_user.id, payload.statement_id)
        if statement is None:
            return no_statement_payload()
        run = AgentRun(
            user_id=current_user.id,
            statement_id=payload.statement_id,
            workflow_name="money_leak_statement_analysis",
            current_step="queued",
            status=AgentRunStatus.RUNNING,
            output_summary=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        background_tasks.add_task(execute_agent_run, run.id, current_user.id, payload.statement_id)
        return success_response({"run_id": str(run.id), "status": "running"}, [])
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/status/{run_id}", response_model=None)
def agent_status(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return the status of a background agent workflow."""
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == current_user.id).first()
        if run is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response("RUN_NOT_FOUND", "Agent run was not found", {}),
            )
        return success_response(serialize_agent_run(run), [])
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.post("/recommend", response_model=None)
def recommend(
    payload: RecommendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return rule-based or AI-enhanced saving recommendations for a statement."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, payload.statement_id)
        if statement is None:
            return no_statement_payload()
        memories = search_memory(current_user.id, payload.context or "budget recommendations", top_k=5)
        rule_based = build_rule_based_recommendations(transactions)
        data = optional_ai_recommendations(rule_based, memories, payload.context)
        warnings = list(rule_based.get("warnings", []))
        if data.get("reason") == "api_key_not_configured":
            warnings.append("AI recommendations are unavailable because ANTHROPIC_API_KEY is not configured")
        return success_response(data, list(dict.fromkeys(warnings)))
    except SQLAlchemyError as exc:
        return database_error_response(exc)
