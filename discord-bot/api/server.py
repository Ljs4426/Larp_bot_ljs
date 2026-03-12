"""REST API — runs in the same event loop as the bot, shares BotDatabase directly.

Auth: X-API-Key header (value from API_KEY in .env). If API_KEY is not set,
all requests are allowed but a warning is logged on startup.

docs: /docs  /redoc
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

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


@app.middleware("http")
async def check_api_key(request: Request, call_next):
    # skip auth for health check so monitoring tools don't need a key
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    expected_key = os.getenv("API_KEY")
    if not expected_key:
        # no key configured — allow everything but this is a security risk
        return await call_next(request)

    provided_key = request.headers.get("X-API-Key")
    if provided_key != expected_key:
        return JSONResponse(
            {"detail": "Invalid or missing API key. Set X-API-Key header."},
            status_code=403
        )

    return await call_next(request)


# response models

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


# routes

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
            "GET /events/week",
            "GET /events/week/summary",
            "GET /events?page=1&per_page=50&since=<ISO>&until=<ISO>",
            "GET /health",
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


@app.get("/user/{roblox_user_id}/ep", response_model=EPRecord)
async def get_user_ep_by_id(roblox_user_id: int, request: Request):
    db = request.app.state.database
    record = await db.get_ep_record(roblox_user_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No EP record found for Roblox user ID {roblox_user_id}"
        )
    return _to_ep_record(record)


@app.get("/user/username/{roblox_username}/ep", response_model=EPRecord)
async def get_user_ep_by_username(roblox_username: str, request: Request):
    db = request.app.state.database
    record = await db.get_ep_record_by_username(roblox_username)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No EP record found for Roblox username '{roblox_username}'"
        )
    return _to_ep_record(record)


@app.get("/users", response_model=PaginatedUsers)
async def list_users(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(50, ge=1, le=100, description="Results per page (max 100)"),
):
    db = request.app.state.database
    all_records = await db.get_all_ep_records()
    all_records.sort(key=lambda r: r["ep"], reverse=True)

    total = len(all_records)
    start = (page - 1) * per_page
    end = start + per_page

    return PaginatedUsers(
        total=total,
        page=page,
        per_page=per_page,
        results=[_to_ep_record(r) for r in all_records[start:end]],
    )


@app.get("/users/leaderboard", response_model=list[LeaderboardEntry])
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


# event models

class EventEntry(BaseModel):
    event_type: str
    ep_awarded: int
    participant_count: int
    participants: List[str]
    not_found: List[str]
    host_discord_name: str
    logged_at: str

class PaginatedEvents(BaseModel):
    total: int
    page: int
    per_page: int
    results: List[EventEntry]

class EventSummary(BaseModel):
    week_start: str
    week_end: str
    total_events: int
    total_ep: int
    unique_members: int
    events_by_type: dict


def _to_event_entry(raw: dict) -> EventEntry:
    participants = raw.get("participants", [])
    return EventEntry(
        event_type=raw.get("event_type", ""),
        ep_awarded=raw.get("ep_awarded", 0),
        participant_count=len(participants),
        participants=participants,
        not_found=raw.get("not_found", []),
        host_discord_name=raw.get("host_discord_name", ""),
        logged_at=raw.get("logged_at", ""),
    )


@app.get("/events/week", response_model=List[EventEntry])
async def events_this_week(request: Request):
    """return all events logged in the current week (sunday 19:00 UTC boundary)"""
    from utils.week import current_week_start, current_week_end
    now = datetime.now(timezone.utc)
    week_start = current_week_start(now)
    week_end   = current_week_end(now)
    db = request.app.state.database
    events = await db.get_events_in_range(week_start, week_end)
    events.sort(key=lambda e: e["logged_at"], reverse=True)
    return [_to_event_entry(e) for e in events]


@app.get("/events/week/summary", response_model=EventSummary)
async def events_week_summary(request: Request):
    """totals and breakdowns for the current week"""
    from utils.week import current_week_start, current_week_end
    from collections import defaultdict
    now = datetime.now(timezone.utc)
    week_start = current_week_start(now)
    week_end   = current_week_end(now)
    db = request.app.state.database
    events = await db.get_events_in_range(week_start, week_end)

    total_ep = sum(e["ep_awarded"] * len(e.get("participants", [])) for e in events)
    unique_members = len({p for e in events for p in e.get("participants", [])})
    by_type: dict = defaultdict(int)
    for e in events:
        by_type[e["event_type"]] += 1

    return EventSummary(
        week_start=week_start.isoformat(),
        week_end=week_end.isoformat(),
        total_events=len(events),
        total_ep=total_ep,
        unique_members=unique_members,
        events_by_type=dict(by_type),
    )


@app.get("/events", response_model=PaginatedEvents)
async def list_events(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(50, ge=1, le=100, description="Results per page (max 100)"),
    since: Optional[str] = Query(None, description="Filter from this ISO datetime (inclusive)"),
    until: Optional[str] = Query(None, description="Filter to this ISO datetime (exclusive)"),
):
    """all events, newest first, with optional date range filter"""
    db = request.app.state.database
    events = await db.get_all_event_log_entries()

    if since:
        try:
            since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since.endswith('Z') or '+' not in since else datetime.fromisoformat(since)
            events = [e for e in events if datetime.fromisoformat(e["logged_at"]) >= since_dt]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'since' datetime: {since}")

    if until:
        try:
            until_dt = datetime.fromisoformat(until).replace(tzinfo=timezone.utc) if until.endswith('Z') or '+' not in until else datetime.fromisoformat(until)
            events = [e for e in events if datetime.fromisoformat(e["logged_at"]) < until_dt]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'until' datetime: {until}")

    events.sort(key=lambda e: e["logged_at"], reverse=True)
    total = len(events)
    start = (page - 1) * per_page
    return PaginatedEvents(
        total=total,
        page=page,
        per_page=per_page,
        results=[_to_event_entry(e) for e in events[start:start + per_page]],
    )


async def start_api(database) -> None:
    """attach db to app and start uvicorn — call with asyncio.create_task()"""
    app.state.database = database

    api_key = os.getenv("API_KEY")
    if not api_key:
        logger.warning(
            "API_KEY is not set — the EP API is open to anyone who can reach the port. "
            "Set API_KEY in .env to require authentication."
        )

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
