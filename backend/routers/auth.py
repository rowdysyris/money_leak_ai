"""Authentication API routes."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import User
from schemas.auth import LoginRequest, RegisterRequest
from schemas.common import success_response
from services.auth_service import authenticate_user, register_user, serialize_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=None)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    """Register a new user and return an access token."""
    data = register_user(db, payload)
    return success_response(data)


@router.post("/login", response_model=None)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """Authenticate a user and return an access token."""
    data = authenticate_user(db, payload)
    return success_response(data)


@router.get("/me", response_model=None)
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user's public profile."""
    return success_response({"user": serialize_user(current_user)})
