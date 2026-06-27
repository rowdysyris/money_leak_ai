"""API router exports for MoneyLeak AI."""

from routers.agents import router as agents_router
from routers.auth import router as auth_router
from routers.budget import router as budget_router
from routers.dashboard import router as dashboard_router
from routers.goals import router as goals_router
from routers.insights import router as insights_router
from routers.rag import router as rag_router
from routers.reports import router as reports_router
from routers.statements import router as statements_router
from routers.transactions import router as transactions_router

__all__ = [
    "agents_router",
    "auth_router",
    "budget_router",
    "dashboard_router",
    "goals_router",
    "insights_router",
    "rag_router",
    "reports_router",
    "statements_router",
    "transactions_router",
]
