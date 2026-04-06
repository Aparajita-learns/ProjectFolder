"""Golden tests for Phase 1 normalization."""

from zomato_ingest.transform import (
    cost_band_from_inr,
    parse_approx_cost,
    parse_cuisines,
    parse_rating,
    transform_record,
)


def test_parse_cuisines_multi_label():
    assert parse_cuisines("North Indian, Mughlai, Chinese") == [
        "north indian",
        "mughlai",
        "chinese",
    ]


def test_parse_rating_standard():
    assert parse_rating("4.1/5") == 4.1


def test_parse_rating_new_is_null():
    assert parse_rating("NEW") is None
    assert parse_rating("-") is None


def test_cost_bands_inr():
    assert cost_band_from_inr(350) == "low"
    assert cost_band_from_inr(800) == "medium"
    assert cost_band_from_inr(1200) == "high"
    assert cost_band_from_inr(None) is None


def test_parse_approx_cost():
    assert parse_approx_cost(800) == 800
    assert parse_approx_cost("Rs.800") == 800
    assert parse_approx_cost(None) is None


def test_transform_record_golden_jalsa_like():
    raw = {
        "url": "https://www.zomato.com/bangalore/jalsa-banashankari",
        "address": "942, 21st Main Road, Bangalore",
        "name": "Jalsa",
        "rate": "4.1/5",
        "votes": "775",
        "location": "Banashankari",
        "rest_type": "Casual Dining",
        "dish_liked": "Pasta, Biryani",
        "cuisines": "North Indian, Mughlai, Chinese",
        "approx_cost(for two people)": 800,
        "reviews_list": [],
        "listed_in(city)": "Banashankari",
    }
    out = transform_record(raw)
    assert out["name"] == "Jalsa"
    assert out["city"] == "Banashankari"
    assert out["area"] == "Banashankari"
    assert out["cuisines"] == ["north indian", "mughlai", "chinese"]
    assert out["rating"] == 4.1
    assert out["approx_cost_for_two"] == 800
    assert out["cost_band"] == "medium"
    assert out["votes"] == 775
    assert len(out["restaurant_id"]) == 32


def test_transform_missing_rating_and_cost():
    raw = {
        "url": "",
        "address": "Somewhere",
        "name": "X",
        "rate": "NEW",
        "votes": None,
        "location": "",
        "rest_type": "",
        "dish_liked": "",
        "cuisines": "Italian",
        "approx_cost(for two people)": None,
        "reviews_list": None,
        "listed_in(city)": "Delhi",
    }
    out = transform_record(raw)
    assert out["rating"] is None
    assert out["approx_cost_for_two"] is None
    assert out["cost_band"] is None
    assert out["cuisines"] == ["italian"]
