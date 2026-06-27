"""add transaction category feedback table and expanded category sources

Revision ID: 0002_category_feedback
Revises: 0001_initial_schema
Create Date: 2026-06-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_category_feedback"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_SOURCE_CHECK = (
    "category_source IS NULL OR category_source IN "
    "('user_rule', 'verified_merchant', 'learned_rule', 'merchant_cache', 'fuzzy_match', "
    "'keyword_rule', 'ml_fallback', 'low_confidence', 'high_value_review')"
)


def upgrade() -> None:
    """Apply the feedback table migration and expand transaction category source values."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        op.drop_constraint("ck_transactions_category_source", "transactions", type_="check")
        op.create_check_constraint("ck_transactions_category_source", "transactions", CATEGORY_SOURCE_CHECK)

    uuid_type = postgresql.UUID(as_uuid=True) if dialect_name == "postgresql" else sa.String(length=36)
    op.create_table(
        "transaction_category_feedback",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("transaction_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("merchant_normalized", sa.String(length=255), nullable=False),
        sa.Column("previous_category", sa.String(length=120), nullable=True),
        sa.Column("corrected_category", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", name="uq_transaction_category_feedback_transaction_id"),
    )
    op.create_index("ix_transaction_category_feedback_transaction_id", "transaction_category_feedback", ["transaction_id"])
    op.create_index("ix_transaction_category_feedback_user_id", "transaction_category_feedback", ["user_id"])
    op.create_index("ix_transaction_category_feedback_merchant_normalized", "transaction_category_feedback", ["merchant_normalized"])
    op.create_index("ix_transaction_category_feedback_corrected_category", "transaction_category_feedback", ["corrected_category"])


def downgrade() -> None:
    """Revert the feedback table migration and restore earlier transaction category source values."""
    op.drop_index("ix_transaction_category_feedback_corrected_category", table_name="transaction_category_feedback")
    op.drop_index("ix_transaction_category_feedback_merchant_normalized", table_name="transaction_category_feedback")
    op.drop_index("ix_transaction_category_feedback_user_id", table_name="transaction_category_feedback")
    op.drop_index("ix_transaction_category_feedback_transaction_id", table_name="transaction_category_feedback")
    op.drop_table("transaction_category_feedback")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_transactions_category_source", "transactions", type_="check")
        op.create_check_constraint(
            "ck_transactions_category_source",
            "transactions",
            "category_source IS NULL OR category_source IN ('user_rule', 'verified_merchant', 'fuzzy_match', 'ml_fallback', 'low_confidence')",
        )
