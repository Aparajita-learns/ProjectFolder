"""Live Groq API checks (max a few calls). Requires GROQ_API_KEY in project-root .env."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GROQ_BASE = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


@pytest.fixture(scope="module", autouse=True)
def _load_dotenv() -> None:
    load_dotenv(_REPO_ROOT / ".env")


def _api_key() -> str:
    return (os.getenv("GROQ_API_KEY") or "").strip()


def _require_groq_key() -> None:
    if not _api_key():
        pytest.skip("GROQ_API_KEY not set — add it to .env at the repository root")


@pytest.mark.integration
def test_groq_api_key_loaded_from_dotenv() -> None:
    _require_groq_key()
    assert len(_api_key()) > 20


@pytest.mark.integration
def test_groq_models_endpoint_authorizes() -> None:
    _require_groq_key()
    r = httpx.get(
        f"{_GROQ_BASE}/models",
        headers={"Authorization": f"Bearer {_api_key()}"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    assert "data" in data and isinstance(data["data"], list)
    assert len(data["data"]) >= 1, "Expected at least one model from Groq /models"


@pytest.mark.integration
def test_groq_chat_completion_smoke() -> None:
    _require_groq_key()
    client = OpenAI(api_key=_api_key(), base_url=_GROQ_BASE)
    resp = client.chat.completions.create(
        model=_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": "You are a terse assistant."},
            {"role": "user", "content": 'Reply with the single word "pong" and nothing else.'},
        ],
        temperature=0,
        max_tokens=32,
    )
    choice = (resp.choices[0].message.content or "").strip()
    assert choice, "Empty completion content"
    assert "pong" in choice.lower(), f"Unexpected reply: {choice!r}"


@pytest.mark.integration
def test_groq_rejects_invalid_key() -> None:
    client = OpenAI(api_key="invalid-key-for-negative-test", base_url=_GROQ_BASE)
    with pytest.raises(APIStatusError) as exc:
        client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=4,
        )
    assert exc.value.status_code in (401, 403)
