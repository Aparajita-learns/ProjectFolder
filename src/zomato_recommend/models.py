"""Phase 3: validated user preferences (API / form body)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

BudgetBand = Literal["low", "medium", "high"]


class UserPreferences(BaseModel):
    """Canonical preference object mapped to the SQLite query layer."""

    location: str = Field(..., min_length=1, max_length=120, description="City / area label matching dataset `city`")
    budget: BudgetBand
    cuisines: list[str] = Field(default_factory=list, description="If empty, no cuisine filter (any cuisine).")
    min_rating: float | None = Field(default=None, ge=0.0, le=5.0)
    additional_preferences: str = Field(default="", max_length=500)
    desired_top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("cuisines", mode="before")
    @classmethod
    def strip_cuisines(cls, v: object) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            parts = [p.strip() for p in v.replace("|", ",").split(",")]
            return [p for p in parts if p]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


def budget_to_cost_bands(budget: BudgetBand) -> list[str]:
    """Map UI budget to exact cost_band filter (strict match)."""
    return [budget]
