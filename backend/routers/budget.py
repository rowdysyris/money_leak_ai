"""Budget API routes for MoneyLeak AI."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import User
from schemas.common import error_response, success_response
from services.budget_service import get_budget_status, update_budget, upsert_budget

router = APIRouter(prefix="/api/budget", tags=["Budget"])


class BudgetPayload(BaseModel):
    """Request body for budget setup and partial budget updates."""

    total_monthly_limit: Decimal | None = Field(default=None, ge=0)
    savings_target: Decimal | None = Field(default=None, ge=0)
    food_budget: Decimal | None = Field(default=None, ge=0)
    shopping_budget: Decimal | None = Field(default=None, ge=0)
    subscriptions_budget: Decimal | None = Field(default=None, ge=0)
    travel_budget: Decimal | None = Field(default=None, ge=0)
    bills_budget: Decimal | None = Field(default=None, ge=0)
    custom_budgets: dict[str, Decimal | float | int] | None = None

    model_config = ConfigDict(extra="ignore")


def payload_to_dict(payload: BudgetPayload) -> dict[str, Any]:
    """Convert a Pydantic budget payload to a dictionary preserving explicitly provided fields."""
    return payload.model_dump(exclude_unset=True)


def service_result_to_response(result: dict[str, Any], success_status: int = 200) -> dict[str, Any] | JSONResponse:
    """Convert a budget service result to the required API envelope."""
    error = result.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", "BUDGET_ERROR"))
        message = str(error.get("message", "Budget operation failed."))
        details = error.get("details", {}) if isinstance(error.get("details", {}), dict) else {}
        response_status = status.HTTP_400_BAD_REQUEST if code == "INVALID_BUDGET" else status.HTTP_500_INTERNAL_SERVER_ERROR
        return JSONResponse(status_code=response_status, content=error_response(code, message, details))
    return JSONResponse(status_code=success_status, content=success_response(result.get("data"), result.get("warnings", [])))


@router.post("/setup", response_model=None)
def setup_budget(
    payload: BudgetPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Create or replace the authenticated user's budget settings with upsert behavior."""
    result = upsert_budget(db, current_user.id, payload_to_dict(payload))
    return service_result_to_response(result)


@router.get("/status", response_model=None)
def read_budget_status(
    month: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return selected-month spending status against the authenticated user's budget."""
    result = get_budget_status(db, current_user.id, month=month)
    return service_result_to_response(result)


@router.get("/suggestions", response_model=None)
def read_budget_suggestions(
    month: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return suggested monthly budget values for the selected month."""
    result = get_budget_status(db, current_user.id, month=month)
    if result.get("error"):
        return service_result_to_response(result)
    data = result.get("data", {}) if isinstance(result.get("data", {}), dict) else {}
    return service_result_to_response({"data": {"suggested_budget": data.get("suggested_budget", {}), "month": data.get("month")}, "warnings": result.get("warnings", [])})


@router.patch("/update", response_model=None)
def patch_budget(
    payload: BudgetPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Partially update the authenticated user's budget settings."""
    result = update_budget(db, current_user.id, payload_to_dict(payload))
    return service_result_to_response(result)
