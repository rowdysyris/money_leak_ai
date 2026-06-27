"""AI merchant discovery fallback, cache, and response tests."""

from sqlalchemy.orm import Session

from database import engine
from services import ai_merchant_discovery as discovery


def test_discovery_without_api_key_is_safe(monkeypatch) -> None:
    monkeypatch.setattr(discovery.settings, "ANTHROPIC_API_KEY", "")
    assert discovery.discover_merchant("BADASTOOR") == {
        "success": False,
        "reason": "no_api_key",
        "category": "Miscellaneous",
        "confidence": 0.0,
    }
    assert discovery.discover_merchant("")["reason"] == "empty_merchant"


def test_cache_round_trip_and_use_count() -> None:
    with Session(engine) as db:
        cached = discovery.cache_merchant(
            db,
            "CACHEMERCHANT99",
            "Groceries",
            city="Bhopal",
            business_name="Cache Merchant",
            business_type="Grocery",
        )
        assert cached is not None
        original_count = cached.use_count
        hit = discovery.check_merchant_cache(db, "CACHEMERCHANT99", "Bhopal")
        assert hit is not None
        assert hit.category == "Groceries"
        assert hit.use_count == original_count + 1
        assert discovery.check_merchant_cache(db, "DOES-NOT-EXIST") is None


def test_cached_result_precedes_api_call(monkeypatch) -> None:
    with Session(engine) as db:
        discovery.cache_merchant(db, "CACHEFIRST99", "Shopping", city="Pune")
        monkeypatch.setattr(discovery, "call_anthropic", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("API called")))
        result = discovery.discover_merchant("CACHEFIRST99", "Pune", db)
        assert result["success"] is True
        assert result["data"]["source"] == "merchant_cache"
        assert result["data"]["category"] == "Shopping"


def test_mocked_ai_response_is_validated_and_cached(monkeypatch) -> None:
    monkeypatch.setattr(discovery.settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        discovery,
        "call_anthropic",
        lambda *_args: {
            "content": [
                {
                    "type": "text",
                    "text": '{"business_name":"Badastoor","business_type":"Restaurant","category":"Food & Dining"}',
                }
            ]
        },
    )
    with Session(engine) as db:
        result = discovery.discover_merchant("AI-MERCHANT-UNIQUE", "Bhopal", db)
        assert result["success"] is True
        assert result["data"]["category"] == "Food & Dining"
        assert discovery.check_merchant_cache(db, "AI-MERCHANT-UNIQUE", "Bhopal") is not None


def test_invalid_ai_json_and_category_fall_back() -> None:
    invalid_json = discovery.parse_ai_json_response("not-json")
    invalid_category = discovery.parse_ai_json_response('{"category":"Cryptocurrency"}')
    assert invalid_json["category"] == "Miscellaneous"
    assert invalid_category["category"] == "Miscellaneous"
