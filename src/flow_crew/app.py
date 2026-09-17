"""Simulator độc lập: dashboard + API, không database, không cần API key.

    .venv/Scripts/python.exe -m uvicorn src.flow_crew.app:app --host 127.0.0.1 --port 8030

Chỉ chạy trên localhost: simulator tin vào vai người duyệt do trình duyệt gửi
lên, điều chấp nhận được trên máy của mình và không ở đâu khác.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from src.flow_crew.api import router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="VinWonder FlowCrew · Simulator", version="0.1.0")
app.include_router(router, prefix="/api/v1/flow-crew", tags=["flow-crew"])


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
