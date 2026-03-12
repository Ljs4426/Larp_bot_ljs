import json
import asyncio
import os
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BotDatabase:
    def __init__(self, file_path: str = "bot_data.json"):
        self.file_path = file_path
        self.lock = asyncio.Lock()
        self.data: Dict[str, List] = {
            "inactivity_notices": [],
            "cooldowns": [],
            "discharge_requests": [],
            "ep_records": [],
            "event_log": [],
            "report_usage": []
        }
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            self._write_sync(self.data)
            logger.info(f"created db file: {self.file_path}")

    def _write_sync(self, data: dict):
        try:
            temp_path = f"{self.file_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            shutil.move(temp_path, self.file_path)
        except Exception as e:
            logger.error(f"db write error: {e}")
            if os.path.exists(f"{self.file_path}.tmp"):
                os.remove(f"{self.file_path}.tmp")
            raise

    async def load(self):
        async with self.lock:
            try:
                if os.path.exists(self.file_path):
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        loaded_data = json.load(f)
                        for key in self.data.keys():
                            if key in loaded_data:
                                self.data[key] = loaded_data[key]
                    logger.info(f"db loaded from {self.file_path}")
                else:
                    logger.warning(f"db file not found: {self.file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"json decode error in {self.file_path}: {e}")
                await self._load_backup()
            except Exception as e:
                logger.error(f"db load error: {e}")

    async def _load_backup(self):
        backup_path = f"{self.file_path}.backup"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"loaded backup: {backup_path}")
            except Exception as e:
                logger.error(f"backup load error: {e}")

    async def _write_data(self):
        try:
            if os.path.exists(self.file_path):
                shutil.copy2(self.file_path, f"{self.file_path}.backup")
            temp_path = f"{self.file_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            shutil.move(temp_path, self.file_path)
            logger.debug("db saved")
        except Exception as e:
            logger.error(f"db save error: {e}")
            if os.path.exists(f"{self.file_path}.tmp"):
                os.remove(f"{self.file_path}.tmp")
            raise

    async def save(self):
        async with self.lock:
            await self._write_data()

    async def add_inactivity_notice(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        reason: str,
        message_id: int,
        is_emergency: bool = False
    ) -> dict:
        notice = {
            "user_id": user_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reason": reason,
            "status": "pending",
            "approver_id": None,
            "message_id": message_id,
            "is_emergency": is_emergency,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.data["inactivity_notices"].append(notice)
        await self.save()
        logger.info(f"inactivity notice added for {user_id}")
        return notice

    async def update_inactivity_status(self, message_id: int, status: str, approver_id: int):
        for notice in self.data["inactivity_notices"]:
            if notice["message_id"] == message_id:
                notice["status"] = status
                notice["approver_id"] = approver_id
                notice["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self.save()
                logger.info(f"inactivity notice {message_id} → {status}")
                return notice
        logger.warning(f"inactivity notice not found: {message_id}")
        return None

    async def get_active_inactivity_notices(self) -> List[dict]:
        current_time = datetime.now(timezone.utc)
        return [
            n for n in self.data["inactivity_notices"]
            if n["status"] == "approved"
            and datetime.fromisoformat(n["end_date"]) > current_time
        ]

    async def get_expired_inactivity_notices(self) -> List[dict]:
        current_time = datetime.now(timezone.utc)
        return [
            n for n in self.data["inactivity_notices"]
            if n["status"] == "approved"
            and datetime.fromisoformat(n["end_date"]) <= current_time
        ]

    async def user_has_active_inactivity(self, user_id: int) -> bool:
        active = await self.get_active_inactivity_notices()
        return any(n["user_id"] == user_id for n in active)

    async def add_cooldown(self, user_id: int, cooldown_end: datetime):
        self.data["cooldowns"].append({
            "user_id": user_id,
            "cooldown_end": cooldown_end.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        await self.save()
        logger.info(f"cooldown added for {user_id} until {cooldown_end}")

    async def get_expired_cooldowns(self) -> List[dict]:
        current_time = datetime.now(timezone.utc)
        return [
            c for c in self.data["cooldowns"]
            if datetime.fromisoformat(c["cooldown_end"]) <= current_time
        ]

    async def remove_cooldown(self, user_id: int):
        self.data["cooldowns"] = [c for c in self.data["cooldowns"] if c["user_id"] != user_id]
        await self.save()
        logger.info(f"cooldown removed for {user_id}")

    async def add_discharge_request(self, user_id: int, reason: str, message_id: int) -> dict:
        request = {
            "user_id": user_id,
            "reason": reason,
            "request_date": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            "approver_id": None,
            "message_id": message_id
        }
        self.data["discharge_requests"].append(request)
        await self.save()
        logger.info(f"discharge request added for {user_id}")
        return request

    async def update_discharge_status(self, message_id: int, status: str, approver_id: int):
        for request in self.data["discharge_requests"]:
            if request["message_id"] == message_id:
                request["status"] = status
                request["approver_id"] = approver_id
                request["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self.save()
                logger.info(f"discharge request {message_id} → {status}")
                return request
        logger.warning(f"discharge request not found: {message_id}")
        return None

    async def cleanup_old_data(self, days: int = 90):
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

        orig_n = len(self.data["inactivity_notices"])
        self.data["inactivity_notices"] = [
            n for n in self.data["inactivity_notices"]
            if datetime.fromisoformat(n.get("created_at", n["start_date"])).timestamp() > cutoff
        ]

        orig_d = len(self.data["discharge_requests"])
        self.data["discharge_requests"] = [
            r for r in self.data["discharge_requests"]
            if datetime.fromisoformat(r["request_date"]).timestamp() > cutoff
        ]

        removed_n = orig_n - len(self.data["inactivity_notices"])
        removed_d = orig_d - len(self.data["discharge_requests"])
        if removed_n or removed_d:
            await self.save()
            logger.info(f"cleanup: -{removed_n} inactivity, -{removed_d} discharge")

    async def get_ep_record(self, roblox_user_id: int) -> Optional[dict]:
        for r in self.data["ep_records"]:
            if r["roblox_user_id"] == roblox_user_id:
                return r
        return None

    async def get_ep_record_by_username(self, roblox_username: str) -> Optional[dict]:
        target = roblox_username.lower()
        for r in self.data["ep_records"]:
            if r["roblox_username"].lower() == target:
                return r
        return None

    async def add_ep_record(
        self,
        roblox_username: str,
        roblox_user_id: int,
        discord_user_id: Optional[int] = None
    ) -> dict:
        record = {
            "roblox_username": roblox_username,
            "roblox_user_id": roblox_user_id,
            "discord_user_id": discord_user_id,
            "ep": 0,
            "join_date": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        self.data["ep_records"].append(record)
        await self.save()
        logger.info(f"EP record added: {roblox_username} ({roblox_user_id})")
        return record

    async def update_ep(self, roblox_user_id: int, delta: int) -> Optional[dict]:
        for r in self.data["ep_records"]:
            if r["roblox_user_id"] == roblox_user_id:
                r["ep"] += delta
                r["last_updated"] = datetime.now(timezone.utc).isoformat()
                await self.save()
                logger.info(f"EP update: {r['roblox_username']} delta={delta:+d} new={r['ep']}")
                return r
        logger.warning(f"EP record not found: roblox_user_id={roblox_user_id}")
        return None

    async def update_ep_by_username(self, roblox_username: str, delta: int) -> Optional[dict]:
        target = roblox_username.lower()
        for r in self.data["ep_records"]:
            if r["roblox_username"].lower() == target:
                r["ep"] += delta
                r["last_updated"] = datetime.now(timezone.utc).isoformat()
                await self.save()
                logger.info(f"EP update: {r['roblox_username']} delta={delta:+d} new={r['ep']}")
                return r
        return None

    async def update_ep_record(self, roblox_user_id: int, fields: dict) -> Optional[dict]:
        for r in self.data["ep_records"]:
            if r["roblox_user_id"] == roblox_user_id:
                r.update(fields)
                r["last_updated"] = datetime.now(timezone.utc).isoformat()
                await self.save()
                return r
        return None

    async def remove_ep_record(self, roblox_user_id: int) -> Optional[dict]:
        for i, r in enumerate(self.data["ep_records"]):
            if r["roblox_user_id"] == roblox_user_id:
                removed = self.data["ep_records"].pop(i)
                await self.save()
                logger.info(f"EP record removed: {removed['roblox_username']} ({roblox_user_id})")
                return removed
        return None

    async def wipe_ep_by_discord_id(self, discord_user_id: int) -> Optional[dict]:
        for i, r in enumerate(self.data["ep_records"]):
            if r.get("discord_user_id") == discord_user_id:
                removed = self.data["ep_records"].pop(i)
                await self.save()
                logger.info(f"EP wiped for discord {discord_user_id} (roblox: {removed['roblox_username']})")
                return removed
        return None

    async def get_all_ep_records(self) -> List[dict]:
        return list(self.data["ep_records"])

    async def add_event_log_entry(
        self,
        event_type: str,
        ep_awarded: int,
        participants: List[str],
        not_found: List[str],
        host_discord_id: int,
        host_discord_name: str,
        screenshot_url: Optional[str] = None,
    ) -> dict:
        entry = {
            "event_type": event_type,
            "ep_awarded": ep_awarded,
            "participants": participants,
            "not_found": not_found,
            "host_discord_id": host_discord_id,
            "host_discord_name": host_discord_name,
            "screenshot_url": screenshot_url,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        self.data["event_log"].append(entry)
        await self.save()
        return entry

    async def get_event_log_since(self, since: datetime) -> List[dict]:
        return [
            e for e in self.data["event_log"]
            if datetime.fromisoformat(e["logged_at"]) >= since
        ]

    async def get_events_in_range(self, since: datetime, until: datetime) -> List[dict]:
        return [
            e for e in self.data["event_log"]
            if since <= datetime.fromisoformat(e["logged_at"]) < until
        ]

    async def add_report_usage(self, discord_user_id: int) -> None:
        self.data["report_usage"].append({
            "discord_user_id": discord_user_id,
            "used_at": datetime.now(timezone.utc).isoformat(),
        })
        await self.save()

    async def get_report_usage_count(self, discord_user_id: int, since: datetime) -> int:
        return sum(
            1 for e in self.data["report_usage"]
            if e["discord_user_id"] == discord_user_id
            and datetime.fromisoformat(e["used_at"]) >= since
        )

    async def sync_ep_records(self, group_members: List[dict]) -> tuple:
        async with self.lock:
            current_ids = {r["roblox_user_id"] for r in self.data["ep_records"]}
            group_ids   = {m["roblox_user_id"] for m in group_members}
            group_map   = {m["roblox_user_id"]: m for m in group_members}

            added: List[dict] = []
            for uid in group_ids - current_ids:
                member = group_map[uid]
                record = {
                    "roblox_username": member["roblox_username"],
                    "roblox_user_id": uid,
                    "discord_user_id": None,
                    "ep": 0,
                    "join_date": datetime.now(timezone.utc).isoformat(),
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
                self.data["ep_records"].append(record)
                added.append(record)

            departed_ids = current_ids - group_ids
            removed: List[dict] = []
            if departed_ids:
                kept, gone = [], []
                for r in self.data["ep_records"]:
                    (gone if r["roblox_user_id"] in departed_ids else kept).append(r)
                self.data["ep_records"] = kept
                removed = gone

            if added or removed:
                await self._write_data()
                logger.info(f"EP sync: +{len(added)} added, -{len(removed)} removed")

            return added, removed
