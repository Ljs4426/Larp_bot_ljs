"""Week boundary helpers — week runs sunday 19:00 utc → next sunday 19:00 utc."""

from datetime import datetime, timedelta, timezone


def current_week_start(reference: datetime = None) -> datetime:
    """most recent sunday at 19:00 utc that is <= reference"""
    if reference is None:
        reference = datetime.now(timezone.utc)
    # Mon=0...Sun=6, so (weekday+1)%7 = days since last sunday
    days_since_sunday = (reference.weekday() + 1) % 7
    candidate = (reference - timedelta(days=days_since_sunday)).replace(
        hour=19, minute=0, second=0, microsecond=0
    )
    if reference < candidate:
        candidate -= timedelta(weeks=1)
    return candidate


def current_week_end(reference: datetime = None) -> datetime:
    return current_week_start(reference) + timedelta(weeks=1)


def week_start_for_date(date_str: str) -> datetime:
    """find week start for a YYYY-MM-DD string"""
    dt = datetime.strptime(date_str, '%Y-%m-%d').replace(
        hour=12, tzinfo=timezone.utc  # noon keeps it safely inside the day
    )
    return current_week_start(dt)


def format_week_range(week_start: datetime) -> str:
    """e.g. '03 Mar 2026 – 10 Mar 2026'"""
    week_end = week_start + timedelta(weeks=1)
    return f"{week_start.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')}"
