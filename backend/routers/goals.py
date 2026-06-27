"""Goal planning API routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import User
from routers.dashboard import database_error_response, fetch_transactions_for_statement, no_statement_payload, service_to_response
from schemas.common import error_response
from services.goal_planner import build_goal_plan

router = APIRouter(prefix="/api/goals", tags=["Goals"])


class GoalPlanRequest(BaseModel):
    """Request body for a goal-based savings plan."""

    goal_name: str = Field(default="Savings goal", max_length=120)
    target_amount: float = Field(default=0, ge=0)
    months: int = Field(default=6, ge=1, le=120)


@router.post("/plan", response_model=None)
def plan_goal(
    payload: GoalPlanRequest,
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return a goal-based savings plan from uploaded statement insights."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(build_goal_plan(transactions, payload.goal_name, payload.target_amount, payload.months))
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    except (TypeError, ValueError) as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response("INVALID_GOAL", "Goal plan input is invalid.", {"error_type": exc.__class__.__name__}),
        )
