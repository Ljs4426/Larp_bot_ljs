"""Loader for events_config.json.

All event names and EP award amounts are defined in that file.
Call load_events() wherever you need the event list — it re-reads
the file on every call so edits take effect without a bot restart.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# events_config.json lives one level above this utils/ directory
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "events_config.json")


def load_events() -> list[dict]:
    """
    Return the list of event dicts from events_config.json.

    Each dict has the shape: {"name": str, "ep_value": int}

    Returns an empty list if the file is missing or malformed.
    """
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        events = data.get("events", [])
        if not isinstance(events, list):
            logger.error("events_config.json: 'events' must be a list")
            return []
        return events
    except FileNotFoundError:
        logger.error(f"events_config.json not found at {_CONFIG_PATH}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"events_config.json is invalid JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading events_config.json: {e}")
        return []


def get_ep_for_event(event_name: str) -> Optional[int]:
    """
    Return the ep_value for an event by name (case-insensitive), or None.
    """
    for event in load_events():
        if event.get("name", "").lower() == event_name.lower():
            return int(event.get("ep_value", 1))
    return None


def is_tryout_event(event_name: str) -> bool:
    """Return True if the event name contains 'tryout' (case-insensitive)."""
    return "tryout" in event_name.lower()
