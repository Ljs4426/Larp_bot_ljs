"""Roblox API integration with caching."""

import aiohttp
import asyncio
import time
import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class RobloxAPICache:
    """
    Roblox API client with caching to reduce API calls.
    
    Caches avatar thumbnails and group icons for 1 hour.
    """
    
    def __init__(self):
        """Initialize the Roblox API client."""
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Dict] = {}
        self.cache_duration = 3600  # 1 hour in seconds
        
        # Placeholder images for fallback
        self.placeholder_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
        self.placeholder_group = "https://cdn.discordapp.com/embed/avatars/1.png"
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]  # Exponential backoff
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _is_cache_fresh(self, cache_key: str) -> bool:
        """
        Check if cache entry is still fresh.
        
        Args:
            cache_key: Key to check in cache
            
        Returns:
            True if cache is fresh and valid
        """
        if cache_key not in self.cache:
            return False
        
        cache_entry = self.cache[cache_key]
        current_time = time.time()
        
        return (current_time - cache_entry['timestamp']) < self.cache_duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        """
        Get URL from cache if fresh.
        
        Args:
            cache_key: Key to retrieve from cache
            
        Returns:
            Cached URL or None if not found/stale
        """
        if self._is_cache_fresh(cache_key):
            return self.cache[cache_key]['url']
        return None
    
    def _set_cache(self, cache_key: str, url: str):
        """
        Store URL in cache with timestamp.
        
        Args:
            cache_key: Key to store in cache
            url: URL to cache
        """
        self.cache[cache_key] = {
            'url': url,
            'timestamp': time.time()
        }
    
    async def _fetch_with_retry(self, url: str) -> Optional[dict]:
        """
        Fetch data from URL with retry logic.
        
        Args:
            url: URL to fetch
            
        Returns:
            JSON response or None on failure
        """
        await self._ensure_session()
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limited
                        logger.warning(f"Roblox API rate limit hit. Attempt {attempt + 1}/{self.max_retries}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delays[attempt])
                    else:
                        logger.error(f"Roblox API returned status {response.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching from Roblox API: {url}. Attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
            except aiohttp.ClientError as e:
                logger.error(f"Client error fetching from Roblox API: {e}. Attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
            except Exception as e:
                logger.error(f"Unexpected error fetching from Roblox API: {e}")
                return None
        
        logger.error(f"Failed to fetch from Roblox API after {self.max_retries} attempts: {url}")
        return None
    
    async def get_user_avatar(self, user_id: int) -> str:
        """
        Get user avatar thumbnail URL.
        
        Args:
            user_id: Roblox user ID
            
        Returns:
            Avatar thumbnail URL (or placeholder on failure)
        """
        cache_key = f"avatar_{user_id}"
        
        # Check cache first
        cached_url = self._get_from_cache(cache_key)
        if cached_url:
            logger.debug(f"Avatar cache hit for user {user_id}")
            return cached_url
        
        # Fetch from API
        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
        
        data = await self._fetch_with_retry(url)
        
        if data and 'data' in data and len(data['data']) > 0:
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                logger.info(f"Successfully fetched avatar for user {user_id}")
                return image_url
        
        # Return placeholder on failure
        logger.warning(f"Using placeholder avatar for user {user_id}")
        return self.placeholder_avatar
    
    async def get_group_icon(self, group_id: int) -> str:
        """
        Get group icon URL.
        
        Args:
            group_id: Roblox group ID
            
        Returns:
            Group icon URL (or placeholder on failure)
        """
        cache_key = f"group_{group_id}"
        
        # Check cache first
        cached_url = self._get_from_cache(cache_key)
        if cached_url:
            logger.debug(f"Group icon cache hit for group {group_id}")
            return cached_url
        
        # Fetch from API
        url = f"https://thumbnails.roblox.com/v1/groups/icons?groupIds={group_id}&size=150x150&format=Png"
        
        data = await self._fetch_with_retry(url)
        
        if data and 'data' in data and len(data['data']) > 0:
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                logger.info(f"Successfully fetched icon for group {group_id}")
                return image_url
        
        # Return placeholder on failure
        logger.warning(f"Using placeholder icon for group {group_id}")
        return self.placeholder_group
    
    async def get_group_members(self, group_id: int) -> list:
        """
        Fetch all members of a Roblox group (handles pagination).

        Args:
            group_id: Roblox group ID

        Returns:
            List of dicts with roblox_user_id, roblox_username, display_name, role
        """
        members = []
        cursor = ""

        while True:
            url = (
                f"https://groups.roblox.com/v1/groups/{group_id}/users"
                f"?sortOrder=Asc&limit=100"
            )
            if cursor:
                url += f"&cursor={cursor}"

            data = await self._fetch_with_retry(url)
            if not data:
                logger.error(f"Failed to fetch group members page for group {group_id}")
                break

            for entry in data.get("data", []):
                user = entry.get("user", {})
                uid = user.get("userId")
                if uid:
                    members.append({
                        "roblox_user_id": uid,
                        "roblox_username": user.get("username", ""),
                        "display_name": user.get("displayName", ""),
                        "role": entry.get("role", {}).get("name", "Member")
                    })

            cursor = data.get("nextPageCursor")
            if not cursor:
                break

            # Brief pause to respect rate limits between pages
            await asyncio.sleep(0.5)

        logger.info(f"Fetched {len(members)} members from group {group_id}")
        return members

    async def get_user_id_by_username(self, username: str) -> int | None:
        """
        Look up a Roblox user ID by username.

        Args:
            username: Roblox username

        Returns:
            User ID integer, or None if not found
        """
        cache_key = f"userid_{username.lower()}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return int(cached)

        await self._ensure_session()
        try:
            async with self.session.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": False},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    users = data.get("data", [])
                    if users:
                        user_id = users[0]["id"]
                        self._set_cache(cache_key, str(user_id))
                        return user_id
                else:
                    logger.error(f"Roblox username lookup returned {response.status} for {username}")
        except Exception as e:
            logger.error(f"Error looking up user ID for {username}: {e}")
        return None

    async def get_username_by_id(self, user_id: int) -> str | None:
        """look up a Roblox username by user ID"""
        cache_key = f"username_{user_id}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        data = await self._fetch_with_retry(f"https://users.roblox.com/v1/users/{user_id}")
        if data and "name" in data:
            self._set_cache(cache_key, data["name"])
            return data["name"]
        return None

    async def get_user_description(self, user_id: int) -> str | None:
        """fetch the live profile description — never cached, we need the latest for verification"""
        await self._ensure_session()
        try:
            url = f"https://users.roblox.com/v1/users/{user_id}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("description", "")
                else:
                    logger.error(f"Roblox profile fetch returned {resp.status} for user {user_id}")
        except asyncio.TimeoutError:
            logger.error(f"timeout fetching Roblox profile for user {user_id}")
        except Exception as e:
            logger.error(f"error fetching Roblox profile for user {user_id}: {e}")
        return None

    def clear_cache(self):
        """Clear all cached entries."""
        self.cache.clear()
        logger.info("Roblox API cache cleared")
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()
        fresh_entries = sum(
            1 for entry in self.cache.values()
            if (current_time - entry['timestamp']) < self.cache_duration
        )
        
        return {
            'total_entries': len(self.cache),
            'fresh_entries': fresh_entries,
            'stale_entries': len(self.cache) - fresh_entries
        }
