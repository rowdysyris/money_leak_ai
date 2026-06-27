"""Agent run tracking model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.common import generate_uuid, utc_now
from models.enums import AgentRunStatus, enum_values


class AgentRun(Base):
    """Execution record for LangGraph agent workflows."""

    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    statement_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("statements.id"), nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(120), nullable=False)
    current_step: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        SAEnum(
            AgentRunStatus,
            name="agent_run_status_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=AgentRunStatus.RUNNING,
    )
    output_summary: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
