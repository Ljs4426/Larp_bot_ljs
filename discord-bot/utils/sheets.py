"""Google Sheets EP sync — runs in executor (gspread is sync)."""

import asyncio
import logging
import os
from typing import List

logger = logging.getLogger(__name__)


async def sync_ep_to_sheet(ep_records: List[dict]) -> bool:
    """write EP records to the configured google sheet, sorted by EP desc"""
    creds_file = os.getenv('GOOGLE_SHEETS_CREDS_FILE')
    sheet_id   = os.getenv('GOOGLE_SHEET_ID')
    if not creds_file or not sheet_id:
        return False
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _write_sheet, creds_file, sheet_id, ep_records)


def _write_sheet(creds_file: str, sheet_id: str, ep_records: List[dict]) -> bool:
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds  = Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets'],
        )
        client = gspread.authorize(creds)
        sheet  = client.open_by_key(sheet_id).sheet1

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
        logger.error(f"sheets sync error: {e}")
        return False
