"""FastAPI: recommend API + static demo UI."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from zomato_recommend.models import UserPreferences
from zomato_recommend.service import run_recommendation

_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

app = FastAPI(title="Zomato-style recommender", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:8765,http://localhost:8765,http://127.0.0.1:8000,http://localhost:8000",
        ).split(",")
        if o.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/recommend")
def recommend(body: UserPreferences) -> dict:
    try:
        return run_recommendation(body)
    except RuntimeError as e:
        if "GROQ_API_KEY" in str(e):
            raise HTTPException(status_code=503, detail="LLM not configured: set GROQ_API_KEY in .env") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


_static_dir = _REPO_ROOT / "phase4_integration" / "static"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_static_dir), name="assets")


@app.get("/")
def index() -> FileResponse:
    index_path = _static_dir / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="UI not found; add phase4_integration/static/index.html")
    return FileResponse(index_path, media_type="text/html")
