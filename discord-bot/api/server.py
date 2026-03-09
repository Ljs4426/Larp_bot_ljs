import os
import logging
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


app = FastAPI(
    title="327th Star Corps EP API",
    description="Read-only access to EP (Engagement Points) records.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class EPRecord(BaseModel):
    roblox_user_id: int
    roblox_username: str
    ep: int
    discord_user_id: Optional[int]
    join_date: str
    last_updated: str

class PaginatedUsers(BaseModel):
    total: int
    page: int
    per_page: int
    results: list[EPRecord]

class LeaderboardEntry(BaseModel):
    rank: int
    roblox_user_id: int
    roblox_username: str
    ep: int
    discord_user_id: Optional[int]


def _to_ep_record(raw: dict) -> EPRecord:
    return EPRecord(
        roblox_user_id=raw["roblox_user_id"],
        roblox_username=raw["roblox_username"],
        ep=raw["ep"],
        discord_user_id=raw.get("discord_user_id"),
        join_date=raw.get("join_date", ""),
        last_updated=raw.get("last_updated", ""),
    )


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "327th Star Corps EP API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "GET /user/{roblox_user_id}/ep",
            "GET /user/username/{roblox_username}/ep",
            "GET /users?page=1&per_page=50",
            "GET /users/leaderboard?limit=10",
            "GET /health",
            "GET /",
        ],
    }


@app.get("/health")
async def health(request: Request):
    db = request.app.state.database
    record_count = len(await db.get_all_ep_records())
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ep_records": record_count,
    }


@app.get(
    "/user/{roblox_user_id}/ep",
    response_model=EPRecord,
    summary="EP record by Roblox user ID",
)
async def get_user_ep_by_id(roblox_user_id: int, request: Request):
    db = request.app.state.database
    record = await db.get_ep_record(roblox_user_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No EP record found for Roblox user ID {roblox_user_id}"
        )
    return _to_ep_record(record)


@app.get(
    "/user/username/{roblox_username}/ep",
    response_model=EPRecord,
    summary="EP record by Roblox username",
)
async def get_user_ep_by_username(roblox_username: str, request: Request):
    db = request.app.state.database
    record = await db.get_ep_record_by_username(roblox_username)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No EP record found for Roblox username '{roblox_username}'"
        )
    return _to_ep_record(record)


@app.get(
    "/users",
    response_model=PaginatedUsers,
    summary="All EP records (paginated)",
)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(50, ge=1, le=200, description="Results per page"),
):
    db = request.app.state.database
    all_records = await db.get_all_ep_records()
    all_records.sort(key=lambda r: r["ep"], reverse=True)

    total = len(all_records)
    start = (page - 1) * per_page
    end = start + per_page
    page_records = all_records[start:end]

    return PaginatedUsers(
        total=total,
        page=page,
        per_page=per_page,
        results=[_to_ep_record(r) for r in page_records],
    )


@app.get(
    "/users/leaderboard",
    response_model=list[LeaderboardEntry],
    summary="EP leaderboard — top N",
)
async def leaderboard(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Number of entries to return"),
):
    db = request.app.state.database
    all_records = await db.get_all_ep_records()
    all_records.sort(key=lambda r: r["ep"], reverse=True)

    return [
        LeaderboardEntry(
            rank=idx + 1,
            roblox_user_id=r["roblox_user_id"],
            roblox_username=r["roblox_username"],
            ep=r["ep"],
            discord_user_id=r.get("discord_user_id"),
        )
        for idx, r in enumerate(all_records[:limit])
    ]


async def start_api(database) -> None:
    app.state.database = database

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8080))

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    server.install_signal_handlers = lambda: None

    logger.info(f"EP API starting on http://{host}:{port}")
    await server.serve()
    logger.info("EP API server stopped")
