"""Google Sheets sync — EP records on Sheet1, event log on a second tab.

Env vars:
  GOOGLE_SHEETS_CREDS_FILE  — path to service account JSON
  GOOGLE_SHEET_ID           — spreadsheet ID (from the URL)
  GOOGLE_EVENT_LOG_TAB      — name of the event log tab (default: "Event Log")
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


def _open_spreadsheet(creds_file: str, sheet_id: str):
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        creds_file,
        scopes=['https://www.googleapis.com/auth/spreadsheets'],
    )
    return gspread.authorize(creds).open_by_key(sheet_id)


def _get_or_create_worksheet(spreadsheet, title: str):
    """return the tab with that name, or create it if it doesn't exist yet"""
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return spreadsheet.add_worksheet(title=title, rows=5000, cols=10)


async def sync_ep_to_sheet(ep_records: List[dict]) -> bool:
    """write EP records to Sheet1, sorted by EP desc"""
    creds_file = os.getenv('GOOGLE_SHEETS_CREDS_FILE')
    sheet_id   = os.getenv('GOOGLE_SHEET_ID')
    if not creds_file or not sheet_id:
        return False
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _write_ep_sheet, creds_file, sheet_id, ep_records)


def _write_ep_sheet(creds_file: str, sheet_id: str, ep_records: List[dict]) -> bool:
    try:
        sheet = _open_spreadsheet(creds_file, sheet_id).sheet1
        sorted_records = sorted(ep_records, key=lambda r: r['ep'], reverse=True)

        rows = [['Rank', 'Roblox Username', 'Roblox User ID', 'EP', 'Discord User ID', 'Last Updated']]
        for rank, r in enumerate(sorted_records, 1):
            rows.append([
                rank,
                r['roblox_username'],
                r['roblox_user_id'],
                r['ep'],
                r.get('discord_user_id') or '',
                r.get('last_updated', ''),
            ])

        sheet.clear()
        sheet.update(rows, 'A1')
        logger.info(f"sheets: wrote {len(sorted_records)} EP records")
        return True
    except ImportError:
        logger.error("gspread or google-auth not installed — sheets sync skipped")
        return False
    except Exception as e:
        logger.error(f"sheets EP sync error: {e}")
        return False


async def sync_events_to_sheet(events: List[dict]) -> bool:
    """write the full event log to the Event Log tab, newest first"""
    creds_file = os.getenv('GOOGLE_SHEETS_CREDS_FILE')
    sheet_id   = os.getenv('GOOGLE_SHEET_ID')
    if not creds_file or not sheet_id:
        return False
    tab_name = os.getenv('GOOGLE_EVENT_LOG_TAB', 'Event Log')
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _write_event_sheet, creds_file, sheet_id, tab_name, events)


def _write_event_sheet(creds_file: str, sheet_id: str, tab_name: str, events: List[dict]) -> bool:
    try:
        spreadsheet = _open_spreadsheet(creds_file, sheet_id)
        sheet = _get_or_create_worksheet(spreadsheet, tab_name)

        sorted_events = sorted(events, key=lambda e: e['logged_at'], reverse=True)

        rows = [['Date (UTC)', 'Event Type', 'Host', 'Attendees', 'EP Each', 'Total EP', 'Participant Names']]
        for e in sorted_events:
            try:
                date_str = datetime.fromisoformat(e['logged_at']).strftime('%Y-%m-%d %H:%M')
            except Exception:
                date_str = e.get('logged_at', '')

            participants = e.get('participants', [])
            rows.append([
                date_str,
                e.get('event_type', ''),
                e.get('host_discord_name', ''),
                len(participants),
                e.get('ep_awarded', 0),
                e.get('ep_awarded', 0) * len(participants),
                ', '.join(participants),
            ])

        sheet.clear()
        sheet.update(rows, 'A1')
        logger.info(f"sheets: wrote {len(sorted_events)} event log entries to '{tab_name}' tab")
        return True
    except ImportError:
        logger.error("gspread or google-auth not installed — event sheet sync skipped")
        return False
    except Exception as e:
        logger.error(f"sheets event sync error: {e}")
        return False
