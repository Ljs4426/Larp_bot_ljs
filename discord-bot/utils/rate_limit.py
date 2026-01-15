"""Rate limiting utilities for Discord bot."""

import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    """
    Rate limiter implementation to prevent command spam.
    
    Tracks command usage per user with configurable limits.
    """
    
    def __init__(self, max_uses: int = 5, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_uses: Maximum number of uses allowed within time window
            time_window: Time window in seconds (default 60 = 1 minute)
        """
        self.max_uses = max_uses
        self.time_window = time_window
        # Structure: {user_id: [(timestamp1, command1), (timestamp2, command2), ...]}
        self.usage_history: Dict[int, list] = defaultdict(list)
    
    def check_rate_limit(self, user_id: int, command_name: str) -> Tuple[bool, int]:
        """
        Check if user has exceeded rate limit for any command.
        
        Args:
            user_id: Discord user ID
            command_name: Name of the command being used
            
        Returns:
            Tuple of (is_allowed: bool, remaining_uses: int)
        """
        current_time = time.time()
        
        # Get user's history
        user_history = self.usage_history[user_id]
        
        # Remove entries older than the time window
        user_history[:] = [
            (timestamp, cmd) for timestamp, cmd in user_history
            if current_time - timestamp < self.time_window
        ]
        
        # Check if user has exceeded limit
        if len(user_history) >= self.max_uses:
            # Calculate when the oldest entry will expire
            oldest_timestamp = user_history[0][0]
            retry_after = int(self.time_window - (current_time - oldest_timestamp)) + 1
            return False, retry_after
        
        # Add current usage
        user_history.append((current_time, command_name))
        
        remaining = self.max_uses - len(user_history)
        return True, remaining
    
    def get_remaining_uses(self, user_id: int) -> int:
        """
        Get remaining uses for a user without incrementing.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Number of remaining uses
        """
        current_time = time.time()
        user_history = self.usage_history[user_id]
        
        # Count recent uses
        recent_uses = sum(
            1 for timestamp, _ in user_history
            if current_time - timestamp < self.time_window
        )
        
        return max(0, self.max_uses - recent_uses)
    
    def reset_user(self, user_id: int) -> None:
        """
        Reset rate limit for a specific user.
        
        Args:
            user_id: Discord user ID
        """
        if user_id in self.usage_history:
            del self.usage_history[user_id]
    
    def cleanup_old_entries(self) -> None:
        """
        Clean up old entries to prevent memory bloat.
        Should be called periodically.
        """
        current_time = time.time()
        
        for user_id in list(self.usage_history.keys()):
            user_history = self.usage_history[user_id]
            user_history[:] = [
                (timestamp, cmd) for timestamp, cmd in user_history
                if current_time - timestamp < self.time_window
            ]
            
            # Remove empty entries
            if not user_history:
                del self.usage_history[user_id]


class CommandCooldown:
    """
    Individual command cooldown tracker.
    
    Tracks cooldowns per user per command.
    """
    
    def __init__(self, cooldown_seconds: int = 10):
        """
        Initialize cooldown tracker.
        
        Args:
            cooldown_seconds: Cooldown duration in seconds
        """
        self.cooldown_seconds = cooldown_seconds
        # Structure: {(user_id, command_name): timestamp}
        self.cooldowns: Dict[Tuple[int, str], float] = {}
    
    def check_cooldown(self, user_id: int, command_name: str) -> Tuple[bool, int]:
        """
        Check if command is on cooldown for user.
        
        Args:
            user_id: Discord user ID
            command_name: Name of the command
            
        Returns:
            Tuple of (is_ready: bool, retry_after: int)
        """
        key = (user_id, command_name)
        current_time = time.time()
        
        if key in self.cooldowns:
            time_passed = current_time - self.cooldowns[key]
            if time_passed < self.cooldown_seconds:
                retry_after = int(self.cooldown_seconds - time_passed) + 1
                return False, retry_after
        
        # Set cooldown
        self.cooldowns[key] = current_time
        return True, 0
    
    def reset_cooldown(self, user_id: int, command_name: str) -> None:
        """
        Reset cooldown for specific user and command.
        
        Args:
            user_id: Discord user ID
            command_name: Name of the command
        """
        key = (user_id, command_name)
        if key in self.cooldowns:
            del self.cooldowns[key]
    
    def cleanup_old_cooldowns(self) -> None:
        """
        Clean up expired cooldowns to prevent memory bloat.
        """
        current_time = time.time()
        
        expired_keys = [
            key for key, timestamp in self.cooldowns.items()
            if current_time - timestamp >= self.cooldown_seconds
        ]
        
        for key in expired_keys:
            del self.cooldowns[key]
