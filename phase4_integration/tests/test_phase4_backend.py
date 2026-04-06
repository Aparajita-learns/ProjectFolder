"""Phase 4 context builder + API smoke with mocks."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from zomato_recommend.app import app
from zomato_recommend.context import build_llm_context, sort_candidates_pre_llm
from zomato_recommend.models import UserPreferences


def test_build_llm_context_empty_candidates() -> None:
    prefs = UserPreferences(location="Delhi", budget="medium")
    ctx = build_llm_context(prefs, [], max_n=10)
    assert ctx["candidate_ids"] == []
    assert "User preferences" in ctx["user_content"]
    assert "```json\n[]\n```" in ctx["user_content"] or "[]" in ctx["user_content"]


def test_build_llm_context_truncates_and_sorts_by_rating() -> None:
    prefs = UserPreferences(location="X", budget="medium")
    rows = [
        {"restaurant_id": "a", "name": "Low", "cuisines": [], "rating": 3.0, "cost_band": "medium", "city": "X"},
        {"restaurant_id": "b", "name": "High", "cuisines": [], "rating": 4.8, "cost_band": "medium", "city": "X"},
        {"restaurant_id": "c", "name": "Mid", "cuisines": [], "rating": 4.0, "cost_band": "medium", "city": "X"},
    ]
    sorted_rows = sort_candidates_pre_llm(rows, "medium")
    assert [r["restaurant_id"] for r in sorted_rows] == ["b", "c", "a"]

    ctx = build_llm_context(prefs, rows, max_n=2)
    assert ctx["candidate_ids"] == ["b", "c"]
    assert "restaurant_id" in ctx["user_content"]
    assert ctx["user_content"].count('"restaurant_id"') == 2


def test_recommend_api_mocked_pipeline() -> None:
    fake = {
        "request_id": "test-uuid",
        "summary": "Nice picks.",
        "results": [
            {
                "restaurant_id": "r1",
                "name": "Test Cafe",
                "cuisines": ["italian"],
                "rating": 4.5,
                "estimated_cost_label": "medium",
                "approx_cost_for_two": 700,
                "explanation": "Because test.",
            }
        ],
        "warnings": [],
        "debug": {"candidates_after_filter": 3, "n_sent_to_llm": 3},
    }
    with patch("zomato_recommend.app.run_recommendation", return_value=fake):
        client = TestClient(app)
        r = client.post(
            "/api/v1/recommend",
            json={
                "location": "Delhi",
                "budget": "medium",
                "cuisines": ["italian"],
                "desired_top_k": 3,
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["request_id"] == "test-uuid"
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Test Cafe"
