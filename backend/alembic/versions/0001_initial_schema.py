"""Create initial MoneyLeak AI schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

profile_type_enum = sa.Enum(
    "Student",
    "Fresher",
    "Working Professional",
    "Freelancer",
    name="profile_type_enum",
    native_enum=False,
    create_constraint=True,
)
processing_status_enum = sa.Enum(
    "pending",
    "processing",
    "completed",
    "failed",
    name="processing_status_enum",
    native_enum=False,
    create_constraint=True,
)
transaction_type_enum = sa.Enum(
    "debit",
    "credit",
    name="transaction_type_enum",
    native_enum=False,
    create_constraint=True,
)
need_want_waste_type_enum = sa.Enum(
    "need",
    "want",
    "waste",
    "savings",
    "unknown",
    name="need_want_waste_type_enum",
    native_enum=False,
    create_constraint=True,
)
transaction_need_want_waste_type_enum = sa.Enum(
    "need",
    "want",
    "waste",
    "savings",
    "unknown",
    name="transaction_need_want_waste_type_enum",
    native_enum=False,
    create_constraint=True,
)
subscription_frequency_enum = sa.Enum(
    "weekly",
    "monthly",
    "yearly",
    "irregular",
    name="subscription_frequency_enum",
    native_enum=False,
    create_constraint=True,
)
cancellation_priority_enum = sa.Enum(
    "high",
    "medium",
    "low",
    name="cancellation_priority_enum",
    native_enum=False,
    create_constraint=True,
)
merchant_source_enum = sa.Enum(
    "ai_discovery",
    "user_correction",
    "verified",
    "learned",
    name="merchant_source_enum",
    native_enum=False,
    create_constraint=True,
)
agent_run_status_enum = sa.Enum(
    "running",
    "completed",
    "failed",
    name="agent_run_status_enum",
    native_enum=False,
    create_constraint=True,
)
savings_difficulty_enum = sa.Enum(
    "easy",
    "medium",
    "hard",
    name="savings_difficulty_enum",
    native_enum=False,
    create_constraint=True,
)


def upgrade() -> None:
    """Apply the initial schema migration."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("profile_type", profile_type_enum, nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("need_want_waste_type", need_want_waste_type_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    categories_table = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("need_want_waste_type", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        categories_table,
        [
            {"name": "Food & Dining", "need_want_waste_type": "want", "is_active": True},
            {"name": "Groceries", "need_want_waste_type": "need", "is_active": True},
            {"name": "Shopping", "need_want_waste_type": "want", "is_active": True},
            {"name": "Subscriptions", "need_want_waste_type": "want", "is_active": True},
            {"name": "Entertainment", "need_want_waste_type": "want", "is_active": True},
            {"name": "Travel & Transport", "need_want_waste_type": "want", "is_active": True},
            {"name": "Rent & Housing", "need_want_waste_type": "need", "is_active": True},
            {"name": "Bills & Utilities", "need_want_waste_type": "need", "is_active": True},
            {"name": "Education", "need_want_waste_type": "need", "is_active": True},
            {"name": "Health & Medical", "need_want_waste_type": "need", "is_active": True},
            {"name": "Personal Care", "need_want_waste_type": "want", "is_active": True},
            {"name": "EMI & Loans", "need_want_waste_type": "need", "is_active": True},
            {"name": "Investments & Savings", "need_want_waste_type": "savings", "is_active": True},
            {"name": "Bank Charges & Fees", "need_want_waste_type": "waste", "is_active": True},
            {"name": "Transfers", "need_want_waste_type": "unknown", "is_active": True},
            {"name": "Cash Withdrawal", "need_want_waste_type": "unknown", "is_active": True},
            {"name": "Miscellaneous", "need_want_waste_type": "unknown", "is_active": True},
        ],
    )

    op.create_table(
        "statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("processed_rows", sa.Integer(), nullable=False),
        sa.Column("skipped_rows", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("processing_status", processing_status_enum, nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("statement_period_start", sa.Date(), nullable=True),
        sa.Column("statement_period_end", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("file_format IN ('csv', 'xlsx', 'xls')", name="ck_statements_file_format"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_statements_user_id"), "statements", ["user_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("transaction_time", sa.Time(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("transaction_type", transaction_type_enum, nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("category_confidence", sa.Float(), nullable=False),
        sa.Column("category_source", sa.String(length=80), nullable=True),
        sa.Column("is_subscription", sa.Boolean(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("is_small_spend", sa.Boolean(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("is_refund", sa.Boolean(), nullable=False),
        sa.Column("is_cashback", sa.Boolean(), nullable=False),
        sa.Column("is_late_night", sa.Boolean(), nullable=False),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        sa.Column("need_want_waste_type", transaction_need_want_waste_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category_source IS NULL OR category_source IN ('user_rule', 'verified_merchant', 'learned_rule', 'merchant_cache', 'fuzzy_match', 'keyword_rule', 'ml_fallback', 'low_confidence', 'high_value_review')",
            name="ck_transactions_category_source",
        ),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_category"), "transactions", ["category"], unique=False)
    op.create_index(op.f("ix_transactions_merchant"), "transactions", ["merchant"], unique=False)
    op.create_index(op.f("ix_transactions_statement_id"), "transactions", ["statement_id"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_date"), "transactions", ["transaction_date"], unique=False)
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("frequency", subscription_frequency_enum, nullable=False),
        sa.Column("average_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("monthly_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("yearly_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("last_charge_date", sa.Date(), nullable=True),
        sa.Column("next_predicted_date", sa.Date(), nullable=True),
        sa.Column("cancellation_priority", cancellation_priority_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscriptions_statement_id"), "subscriptions", ["statement_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)

    op.create_table(
        "duplicate_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id_1", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id_2", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("duplicate_date", sa.Date(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["transaction_id_1"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["transaction_id_2"], ["transactions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "merchant_discovery_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_merchant_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_merchant_name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=False),
        sa.Column("discovered_name", sa.String(length=255), nullable=True),
        sa.Column("business_type", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("source", merchant_source_enum, nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_merchant_discovery_cache_raw_merchant_name"), "merchant_discovery_cache", ["raw_merchant_name"], unique=False)

    op.create_table(
        "user_category_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_normalized", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_category_rules_merchant_normalized"), "user_category_rules", ["merchant_normalized"], unique=False)
    op.create_index(op.f("ix_user_category_rules_user_id"), "user_category_rules", ["user_id"], unique=False)

    op.create_table(
        "learned_merchant_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("merchant_normalized", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("correction_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learned_merchant_rules_merchant_normalized"), "learned_merchant_rules", ["merchant_normalized"], unique=True)

    op.create_table(
        "user_budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_monthly_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("savings_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("food_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("shopping_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("subscriptions_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("travel_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("bills_budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("custom_budgets", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_name", sa.String(length=120), nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=False),
        sa.Column("status", agent_run_status_enum, nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rag_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("faiss_index_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_memories_user_id"), "rag_memories", ["user_id"], unique=False)

    op.create_table(
        "savings_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("target_category", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("possible_monthly_saving", sa.Numeric(12, 2), nullable=False),
        sa.Column("possible_yearly_saving", sa.Numeric(12, 2), nullable=False),
        sa.Column("difficulty", savings_difficulty_enum, nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Reverse the initial schema migration."""
    op.drop_table("savings_recommendations")
    op.drop_index(op.f("ix_rag_memories_user_id"), table_name="rag_memories")
    op.drop_table("rag_memories")
    op.drop_table("agent_runs")
    op.drop_table("user_budgets")
    op.drop_index(op.f("ix_learned_merchant_rules_merchant_normalized"), table_name="learned_merchant_rules")
    op.drop_table("learned_merchant_rules")
    op.drop_index(op.f("ix_user_category_rules_user_id"), table_name="user_category_rules")
    op.drop_index(op.f("ix_user_category_rules_merchant_normalized"), table_name="user_category_rules")
    op.drop_table("user_category_rules")
    op.drop_index(op.f("ix_merchant_discovery_cache_raw_merchant_name"), table_name="merchant_discovery_cache")
    op.drop_table("merchant_discovery_cache")
    op.drop_table("duplicate_payments")
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_statement_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_transaction_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_statement_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_merchant"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_statements_user_id"), table_name="statements")
    op.drop_table("statements")
    op.drop_table("categories")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
