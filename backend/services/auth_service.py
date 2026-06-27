"""Authentication service functions for registration, login, and JWT handling."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from typing import NoReturn
from uuid import UUID

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_settings
from models import User
from schemas.auth import LoginRequest, RegisterRequest, UserPublic

settings = get_settings()
HASH_SCHEME = "pbkdf2_sha256"
HASH_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    """Hash a plaintext password using salted PBKDF2-SHA256."""
    salt_hex = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        bytes.fromhex(salt_hex),
        HASH_ITERATIONS,
    )
    return f"{HASH_SCHEME}${HASH_ITERATIONS}${salt_hex}${digest.hex()}"


def verify_pbkdf2_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-SHA256 hash."""
    try:
        scheme, iterations_text, salt_hex, digest_hex = str(hashed_password).split("$", 3)
        if scheme != HASH_SCHEME:
            return False
        iterations = int(iterations_text)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            str(plain_password).encode("utf-8"),
            bytes.fromhex(salt_hex),
            iterations,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def verify_legacy_bcrypt_password(plain_password: str, hashed_password: str) -> bool:
    """Verify legacy bcrypt hashes when passlib is available and compatible."""
    try:
        from passlib.context import CryptContext

        legacy_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if legacy_context.verify(hashlib.sha256(str(plain_password).encode("utf-8")).hexdigest(), hashed_password):
            return True
        return legacy_context.verify(plain_password, hashed_password)
    except (ImportError, ValueError, TypeError, RuntimeError, AttributeError):
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when a plaintext password matches a stored password hash."""
    stored_hash = str(hashed_password or "")
    if stored_hash.startswith(f"{HASH_SCHEME}$"):
        return verify_pbkdf2_password(plain_password, stored_hash)
    return verify_legacy_bcrypt_password(plain_password, stored_hash)


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for a subject identifier."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def build_api_exception(status_code: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    """Build an HTTPException carrying the standard API error payload fields."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details or {}},
    )


def raise_api_error(status_code: int, code: str, message: str, details: dict | None = None) -> NoReturn:
    """Raise an HTTPException carrying the standard API error payload fields."""
    raise build_api_exception(status_code, code, message, details)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return a user by email address when it exists."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Return a user by primary key when it exists."""
    return db.query(User).filter(User.id == user_id).first()


def serialize_user(user: User) -> dict:
    """Serialize a User ORM object into public API fields."""
    return UserPublic.model_validate(user).model_dump(mode="json")


def build_auth_response(user: User) -> dict:
    """Build auth response data containing token metadata and user details."""
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "user": serialize_user(user),
    }


def register_user(db: Session, payload: RegisterRequest) -> dict:
    """Register a new user and return token response data."""
    existing_user = get_user_by_email(db, payload.email)
    if existing_user is not None:
        raise_api_error(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "Email already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        profile_type=payload.profile_type,
        city=payload.city,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise build_api_exception(status.HTTP_409_CONFLICT, "EMAIL_EXISTS", "Email already exists") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise build_api_exception(status.HTTP_500_INTERNAL_SERVER_ERROR, "DATABASE_ERROR", "Database operation failed") from exc
    return build_auth_response(user)


def authenticate_user(db: Session, payload: LoginRequest) -> dict:
    """Authenticate credentials and return token response data."""
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise_api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS", "Invalid email or password")
    return build_auth_response(user)


def decode_access_token(token: str) -> UUID:
    """Decode a bearer token and return the embedded user id."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise_api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Invalid authentication token")
        return UUID(str(subject))
    except ValueError as exc:
        raise build_api_exception(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Invalid authentication token") from exc
    except JWTError as exc:
        raise build_api_exception(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Invalid authentication token") from exc


def get_authenticated_user(db: Session, token: str) -> User:
    """Return the authenticated user represented by a bearer token."""
    user_id = decode_access_token(token)
    user = get_user_by_id(db, user_id)
    if user is None:
        raise_api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_TOKEN", "Invalid authentication token")
    return user
