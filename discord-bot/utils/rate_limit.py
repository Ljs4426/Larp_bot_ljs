import time
import json
import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """tracks per-user command usage and blocks if they go over the limit"""

    def __init__(self, max_uses: int = 5, time_window: int = 60, persist_path: str = None):
        self.max_uses = max_uses
        self.time_window = time_window
        self.persist_path = persist_path
        # {user_id: [(timestamp, command_name), ...]}
        self.usage_history: dict = defaultdict(list)
        # load saved history so limits survive bot restarts
        if persist_path:
            self.load_from_file(persist_path)

    def check_rate_limit(self, user_id: int, command_name: str) -> tuple:
        """returns (allowed: bool, retry_after_seconds: int)"""
        now = time.time()
        history = self.usage_history[user_id]

        # drop anything older than the window
        history[:] = [
            (ts, cmd) for ts, cmd in history
            if now - ts < self.time_window
        ]

        if len(history) >= self.max_uses:
            oldest = history[0][0]
            retry_after = int(self.time_window - (now - oldest)) + 1
            return False, retry_after

        history.append((now, command_name))
        remaining = self.max_uses - len(history)
        # save to disk so this persists across restarts
        if self.persist_path:
            self.save_to_file(self.persist_path)
        return True, remaining

    def get_remaining_uses(self, user_id: int) -> int:
        now = time.time()
        history = self.usage_history[user_id]
        recent = sum(1 for ts, _ in history if now - ts < self.time_window)
        return max(0, self.max_uses - recent)

    def reset_user(self, user_id: int) -> None:
        if user_id in self.usage_history:
            del self.usage_history[user_id]

    def cleanup_old_entries(self) -> None:
        """prune stale entries so memory doesn't grow forever"""
        now = time.time()
        for user_id in list(self.usage_history.keys()):
            history = self.usage_history[user_id]
            history[:] = [(ts, cmd) for ts, cmd in history if now - ts < self.time_window]
            if not history:
                del self.usage_history[user_id]

    def save_to_file(self, path: str) -> None:
        """write usage history to disk so limits survive a bot restart"""
        try:
            # convert keys to strings for JSON, and list of [ts, cmd] pairs
            data = {
                str(uid): [[ts, cmd] for ts, cmd in entries]
                for uid, entries in self.usage_history.items()
            }
            tmp = path + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            os.replace(tmp, path)
        except Exception as e:
            logger.error(f"rate limiter save failed: {e}")

    def load_from_file(self, path: str) -> None:
        """load usage history from disk on startup"""
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            now = time.time()
            for uid_str, entries in data.items():
                uid = int(uid_str)
                # only restore entries that are still within the window
                valid = [(ts, cmd) for ts, cmd in entries if now - ts < self.time_window]
                if valid:
                    self.usage_history[uid] = valid
            logger.info(f"rate limit history loaded from {path}")
        except Exception as e:
            logger.error(f"rate limiter load failed: {e}")


class CommandCooldown:
    """per-command cooldown for a single user — simpler than RateLimiter"""

    def __init__(self, cooldown_seconds: int = 10):
        self.cooldown_seconds = cooldown_seconds
        # {(user_id, command_name): timestamp}
        self.cooldowns: dict = {}

    def check_cooldown(self, user_id: int, command_name: str) -> tuple:
        """returns (ready: bool, retry_after: int)"""
        key = (user_id, command_name)
        now = time.time()

        if key in self.cooldowns:
            elapsed = now - self.cooldowns[key]
            if elapsed < self.cooldown_seconds:
                retry_after = int(self.cooldown_seconds - elapsed) + 1
                return False, retry_after

        self.cooldowns[key] = now
        return True, 0

    def reset_cooldown(self, user_id: int, command_name: str) -> None:
        key = (user_id, command_name)
        if key in self.cooldowns:
            del self.cooldowns[key]

    def cleanup_old_cooldowns(self) -> None:
        now = time.time()
        expired = [
            key for key, ts in self.cooldowns.items()
            if now - ts >= self.cooldown_seconds
        ]
        for key in expired:
            del self.cooldowns[key]
