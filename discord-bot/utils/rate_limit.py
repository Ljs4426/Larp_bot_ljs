import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, max_uses: int = 5, time_window: int = 60):
        self.max_uses = max_uses
        self.time_window = time_window
        self.usage_history: Dict[int, list] = defaultdict(list)

    def check_rate_limit(self, user_id: int, command_name: str) -> Tuple[bool, int]:
        current_time = time.time()
        user_history = self.usage_history[user_id]

        user_history[:] = [
            (timestamp, cmd) for timestamp, cmd in user_history
            if current_time - timestamp < self.time_window
        ]

        if len(user_history) >= self.max_uses:
            oldest_timestamp = user_history[0][0]
            retry_after = int(self.time_window - (current_time - oldest_timestamp)) + 1
            return False, retry_after

        user_history.append((current_time, command_name))
        remaining = self.max_uses - len(user_history)
        return True, remaining

    def get_remaining_uses(self, user_id: int) -> int:
        current_time = time.time()
        user_history = self.usage_history[user_id]
        recent_uses = sum(
            1 for timestamp, _ in user_history
            if current_time - timestamp < self.time_window
        )
        return max(0, self.max_uses - recent_uses)

    def reset_user(self, user_id: int) -> None:
        if user_id in self.usage_history:
            del self.usage_history[user_id]

    def cleanup_old_entries(self) -> None:
        current_time = time.time()
        for user_id in list(self.usage_history.keys()):
            user_history = self.usage_history[user_id]
            user_history[:] = [
                (timestamp, cmd) for timestamp, cmd in user_history
                if current_time - timestamp < self.time_window
            ]
            if not user_history:
                del self.usage_history[user_id]


class CommandCooldown:
    def __init__(self, cooldown_seconds: int = 10):
        self.cooldown_seconds = cooldown_seconds
        self.cooldowns: Dict[Tuple[int, str], float] = {}

    def check_cooldown(self, user_id: int, command_name: str) -> Tuple[bool, int]:
        key = (user_id, command_name)
        current_time = time.time()

        if key in self.cooldowns:
            time_passed = current_time - self.cooldowns[key]
            if time_passed < self.cooldown_seconds:
                retry_after = int(self.cooldown_seconds - time_passed) + 1
                return False, retry_after

        self.cooldowns[key] = current_time
        return True, 0

    def reset_cooldown(self, user_id: int, command_name: str) -> None:
        key = (user_id, command_name)
        if key in self.cooldowns:
            del self.cooldowns[key]

    def cleanup_old_cooldowns(self) -> None:
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.cooldowns.items()
            if current_time - timestamp >= self.cooldown_seconds
        ]
        for key in expired_keys:
            del self.cooldowns[key]
