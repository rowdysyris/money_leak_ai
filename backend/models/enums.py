"""Application enum definitions used by ORM models and schemas."""

from enum import Enum
from typing import TypeVar

EnumType = TypeVar("EnumType", bound=Enum)


class ProfileType(str, Enum):
    """Supported user profile types."""

    STUDENT = "Student"
    FRESHER = "Fresher"
    WORKING_PROFESSIONAL = "Working Professional"
    FREELANCER = "Freelancer"


class ProcessingStatus(str, Enum):
    """Statement processing lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionType(str, Enum):
    """Supported transaction directions."""

    DEBIT = "debit"
    CREDIT = "credit"


class NeedWantWasteType(str, Enum):
    """Financial behavior labels used for categories and transactions."""

    NEED = "need"
    WANT = "want"
    WASTE = "waste"
    SAVINGS = "savings"
    UNKNOWN = "unknown"


class SubscriptionFrequency(str, Enum):
    """Supported recurring payment frequency labels."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    IRREGULAR = "irregular"


class CancellationPriority(str, Enum):
    """Priority levels for subscription cancellation recommendations."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MerchantSource(str, Enum):
    """Sources for merchant discovery and correction cache records."""

    AI_DISCOVERY = "ai_discovery"
    USER_CORRECTION = "user_correction"
    VERIFIED = "verified"
    LEARNED = "learned"


class AgentRunStatus(str, Enum):
    """Agent workflow execution states."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SavingsDifficulty(str, Enum):
    """Difficulty labels for savings recommendations."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


def enum_values(enum_class: type[EnumType]) -> list[str]:
    """Return enum values for SQLAlchemy string enum persistence."""
    return [member.value for member in enum_class]
