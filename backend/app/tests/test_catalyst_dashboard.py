from app.api.routes_catalysts import _direction, _importance


def test_direction_maps_locked_grades() -> None:
    assert _direction("A+ Bullish") == "bullish"
    assert _direction("A Bearish") == "bearish"
    assert _direction("No Fresh Catalyst") == "neutral"


def test_importance_rewards_direct_high_confidence_a_tier() -> None:
    strong = _importance(
        {
            "catalyst_quality_direction": "A Bullish",
            "source_confidence": "High",
            "direct_sympathy_sector_move": "Direct",
            "action_priority": "High-Conviction Watch",
            "freshness_catalyst_age": "Same-day fresh",
        }
    )
    weak = _importance(
        {
            "catalyst_quality_direction": "No Fresh Catalyst",
            "source_confidence": "Low",
            "direct_sympathy_sector_move": "None",
            "action_priority": "Avoid",
            "freshness_catalyst_age": "Catalyst unverified",
        }
    )
    assert strong > weak
    assert 10 <= weak <= 100
    assert 10 <= strong <= 100
