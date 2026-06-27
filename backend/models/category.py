"""Master category model and seed data for MoneyLeak AI."""

from sqlalchemy import Boolean, Integer, String, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.enums import NeedWantWasteType, enum_values

DEFAULT_CATEGORIES: list[dict[str, str]] = [
    {"name": "Food & Dining", "need_want_waste_type": "want"},
    {"name": "Groceries", "need_want_waste_type": "need"},
    {"name": "Shopping", "need_want_waste_type": "want"},
    {"name": "Subscriptions", "need_want_waste_type": "want"},
    {"name": "Entertainment", "need_want_waste_type": "want"},
    {"name": "Travel & Transport", "need_want_waste_type": "want"},
    {"name": "Rent & Housing", "need_want_waste_type": "need"},
    {"name": "Bills & Utilities", "need_want_waste_type": "need"},
    {"name": "Education", "need_want_waste_type": "need"},
    {"name": "Health & Medical", "need_want_waste_type": "need"},
    {"name": "Personal Care", "need_want_waste_type": "want"},
    {"name": "EMI & Loans", "need_want_waste_type": "need"},
    {"name": "Investments & Savings", "need_want_waste_type": "savings"},
    {"name": "Bank Charges & Fees", "need_want_waste_type": "waste"},
    {"name": "Transfers", "need_want_waste_type": "unknown"},
    {"name": "Cash Withdrawal", "need_want_waste_type": "unknown"},
    {"name": "Miscellaneous", "need_want_waste_type": "unknown"},
]


class Category(Base):
    """Master category record used by categorization and budgeting flows."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    need_want_waste_type: Mapped[NeedWantWasteType] = mapped_column(
        SAEnum(
            NeedWantWasteType,
            name="need_want_waste_type_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


def seed_categories_after_create(target: object, connection: Connection, **kwargs: object) -> None:
    """Seed the categories table immediately after metadata-based table creation."""
    connection.execute(Category.__table__.insert(), DEFAULT_CATEGORIES)


event.listen(Category.__table__, "after_create", seed_categories_after_create)
