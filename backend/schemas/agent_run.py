"""Pydantic schemas for agent runs."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from models.enums import AgentRunStatus
from schemas.base import OrmSchema


class AgentRunBase(OrmSchema):
    """Shared agent run fields."""

    user_id: UUID | None = None
    statement_id: UUID | None = None
    workflow_name: str | None = Field(default=None, max_length=120)
    current_step: str | None = Field(default=None, max_length=120)
    status: AgentRunStatus | None = None
    output_summary: dict[str, object] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRunCreate(AgentRunBase):
    """Agent run creation schema."""


class AgentRunRead(AgentRunBase):
    """Agent run read schema."""

    id: UUID | None = None
