"""Reusable FastAPI dependencies for MoneyLeak AI."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User
from services.auth_service import get_authenticated_user, raise_api_error

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_api_error(401, "NOT_AUTHENTICATED", "Authentication credentials were not provided")
    return get_authenticated_user(db, credentials.credentials)
