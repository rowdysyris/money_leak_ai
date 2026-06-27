"""Optional AI-backed merchant discovery with deterministic fallbacks."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config import get_settings
from models import MerchantDiscoveryCache
from models.common import utc_now
from services.merchant_intelligence import ALLOWED_CATEGORIES, is_allowed_category, normalize_merchant

logger = logging.getLogger("moneyleak-ai.ai_merchant_discovery")
settings = get_settings()
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


def build_discovery_prompt(merchant_name: str, city: str | None = None) -> str:
    """Build a strict JSON-only merchant discovery prompt."""
    location = city or "India"
    categories = ", ".join(ALLOWED_CATEGORIES)
    return (
        f"What type of business is '{merchant_name}' in {location}?\n"
        "Reply in JSON only: {\"business_name\": \"\", \"business_type\": \"\", \"category\": \"\"}\n"
        f"Category must be exactly one of: {categories}\n"
        "If unknown, use Miscellaneous."
    )


def build_failure(reason: str) -> dict[str, Any]:
    """Build a deterministic merchant discovery failure response."""
    return {"success": False, "reason": reason, "category": "Miscellaneous", "confidence": 0.0}


def build_success(data: dict[str, Any], source: str = "ai_discovery") -> dict[str, Any]:
    """Build a deterministic merchant discovery success response."""
    category = str(data.get("category") or "Miscellaneous")
    if not is_allowed_category(category):
        category = "Miscellaneous"
    return {
        "success": True,
        "data": {
            "business_name": str(data.get("business_name") or ""),
            "business_type": str(data.get("business_type") or ""),
            "category": category,
            "source": source,
        },
        "warnings": [],
    }


def get_cached_discovery(db: Session | None, merchant_name: str, city: str | None = None) -> MerchantDiscoveryCache | None:
    """Return an existing merchant discovery cache entry when available."""
    if db is None:
        return None
    normalized = normalize_merchant(merchant_name)
    if not normalized:
        return None
    try:
        query = db.query(MerchantDiscoveryCache).filter(MerchantDiscoveryCache.normalized_merchant_name == normalized)
        if city:
            query = query.filter(MerchantDiscoveryCache.city == city)
        cached = query.order_by(MerchantDiscoveryCache.created_at.desc()).first()
        if cached is not None:
            cached.use_count = int(cached.use_count or 0) + 1
            cached.last_verified_at = utc_now()
            db.commit()
        return cached
    except SQLAlchemyError as exc:
        logger.warning("Merchant discovery cache lookup failed: %s", exc.__class__.__name__)
        return None


def parse_ai_json_response(response_text: str) -> dict[str, Any]:
    """Parse an AI JSON response and return a Miscellaneous fallback when parsing fails."""
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return {"business_name": "", "business_type": "", "category": "Miscellaneous"}
    if not isinstance(parsed, dict):
        return {"business_name": "", "business_type": "", "category": "Miscellaneous"}
    category = str(parsed.get("category") or "Miscellaneous")
    if not is_allowed_category(category):
        category = "Miscellaneous"
    return {
        "business_name": str(parsed.get("business_name") or ""),
        "business_type": str(parsed.get("business_type") or ""),
        "category": category,
    }


def extract_text_from_anthropic_response(payload: dict[str, Any]) -> str:
    """Extract the first text block from an Anthropic response payload."""
    content = payload.get("content", [])
    if not isinstance(content, list):
        return ""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text") or "")
    return ""


def save_discovery_cache(
    db: Session | None,
    merchant_name: str,
    city: str | None,
    discovery_data: dict[str, Any],
) -> None:
    """Persist an AI merchant discovery result when a database session is available."""
    if db is None:
        return
    normalized = normalize_merchant(merchant_name)
    if not normalized:
        return
    try:
        cache_entry = MerchantDiscoveryCache(
            raw_merchant_name=merchant_name,
            normalized_merchant_name=normalized,
            city=city,
            discovered_name=str(discovery_data.get("business_name") or "") or None,
            business_type=str(discovery_data.get("business_type") or "") or None,
            category=str(discovery_data.get("category") or "Miscellaneous"),
            source="ai_discovery",
            confidence_score=0.55 if discovery_data.get("category") == "Miscellaneous" else 0.72,
        )
        db.add(cache_entry)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Merchant discovery cache save failed: %s", exc.__class__.__name__)


def check_merchant_cache(db: Session | None, merchant_name: str, city: str | None = None) -> MerchantDiscoveryCache | None:
    """Public cache lookup used by integration code and tests."""
    return get_cached_discovery(db, merchant_name, city)


def cache_merchant(
    db: Session | None,
    merchant_name: str,
    category: str,
    city: str | None = None,
    business_name: str | None = None,
    business_type: str | None = None,
) -> MerchantDiscoveryCache | None:
    """Persist or update a validated merchant discovery cache entry."""
    if db is None:
        return None
    normalized = normalize_merchant(merchant_name)
    if not normalized:
        return None
    safe_category = category if is_allowed_category(category) else "Miscellaneous"
    try:
        existing = (
            db.query(MerchantDiscoveryCache)
            .filter(
                MerchantDiscoveryCache.normalized_merchant_name == normalized,
                MerchantDiscoveryCache.city == city,
            )
            .first()
        )
        if existing is None:
            existing = MerchantDiscoveryCache(
                raw_merchant_name=merchant_name,
                normalized_merchant_name=normalized,
                city=city,
                discovered_name=business_name,
                business_type=business_type,
                category=safe_category,
                source="ai_discovery",
                confidence_score=0.55 if safe_category == "Miscellaneous" else 0.72,
            )
            db.add(existing)
        else:
            existing.category = safe_category
            existing.discovered_name = business_name or existing.discovered_name
            existing.business_type = business_type or existing.business_type
            existing.last_verified_at = utc_now()
        db.commit()
        db.refresh(existing)
        return existing
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Merchant cache update failed: %s", exc.__class__.__name__)
        return None


def call_anthropic(prompt: str, api_key: str) -> dict[str, Any]:
    """Call Anthropic Messages API with a strict timeout and return the JSON response payload."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 160,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=settings.AI_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.post(ANTHROPIC_MESSAGES_URL, headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def discover_merchant(merchant_name: str, city: str | None = None, db: Session | None = None) -> dict[str, Any]:
    """Discover a merchant category through cache first and optional Anthropic API second."""
    normalized = normalize_merchant(merchant_name)
    if not normalized:
        return build_failure("empty_merchant")

    cached = get_cached_discovery(db, merchant_name, city)
    if cached is not None:
        return build_success(
            {
                "business_name": cached.discovered_name or cached.raw_merchant_name,
                "business_type": cached.business_type or "",
                "category": cached.category,
            },
            source="merchant_cache",
        )

    api_key = settings.ANTHROPIC_API_KEY.strip()
    if not api_key:
        return build_failure("no_api_key")

    prompt = build_discovery_prompt(merchant_name, city)
    try:
        payload = call_anthropic(prompt, api_key)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("AI merchant discovery failed: %s", exc.__class__.__name__)
        return build_failure("api_error")

    response_text = extract_text_from_anthropic_response(payload)
    parsed = parse_ai_json_response(response_text)
    save_discovery_cache(db, merchant_name, city, parsed)
    return build_success(parsed, source="ai_discovery")
