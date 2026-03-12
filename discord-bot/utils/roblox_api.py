import aiohttp
import asyncio
import time
import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class RobloxAPICache:
    """Roblox API client with 1-hour caching for avatars and group icons."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Dict] = {}
        self.cache_duration = 3600

        self.placeholder_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
        self.placeholder_group  = "https://cdn.discordapp.com/embed/avatars/1.png"

        self.max_retries   = 3
        self.retry_delays  = [1, 2, 4]

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _is_cache_fresh(self, cache_key: str) -> bool:
        if cache_key not in self.cache:
            return False
        return (time.time() - self.cache[cache_key]['timestamp']) < self.cache_duration

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        if self._is_cache_fresh(cache_key):
            return self.cache[cache_key]['url']
        return None

    def _set_cache(self, cache_key: str, url: str):
        self.cache[cache_key] = {'url': url, 'timestamp': time.time()}

    async def _fetch_with_retry(self, url: str) -> Optional[dict]:
        await self._ensure_session()
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 429:
                        logger.warning(f"Roblox API rate limit hit (attempt {attempt + 1})")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delays[attempt])
                    else:
                        logger.error(f"Roblox API status {resp.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.error(f"timeout on Roblox API (attempt {attempt + 1}): {url}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
            except aiohttp.ClientError as e:
                logger.error(f"client error on Roblox API (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
            except Exception as e:
                logger.error(f"unexpected error on Roblox API: {e}")
                return None
        logger.error(f"Roblox API failed after {self.max_retries} attempts: {url}")
        return None

    async def get_user_avatar(self, user_id: int) -> str:
        cache_key = f"avatar_{user_id}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        url  = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
        data = await self._fetch_with_retry(url)
        if data and data.get('data'):
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                return image_url
        return self.placeholder_avatar

    async def get_group_icon(self, group_id: int) -> str:
        cache_key = f"group_{group_id}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        url  = f"https://thumbnails.roblox.com/v1/groups/icons?groupIds={group_id}&size=150x150&format=Png"
        data = await self._fetch_with_retry(url)
        if data and data.get('data'):
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                return image_url
        return self.placeholder_group

    async def get_group_members(self, group_id: int) -> list:
        """fetch all members of a group, handles pagination automatically"""
        members = []
        cursor  = ""
        while True:
            url = (
                f"https://groups.roblox.com/v1/groups/{group_id}/users"
                f"?sortOrder=Asc&limit=100"
            )
            if cursor:
                url += f"&cursor={cursor}"
            data = await self._fetch_with_retry(url)
            if not data:
                logger.error(f"failed to fetch group members page for group {group_id}")
                break
            for entry in data.get("data", []):
                user = entry.get("user", {})
                uid  = user.get("userId")
                if uid:
                    members.append({
                        "roblox_user_id":  uid,
                        "roblox_username": user.get("username", ""),
                        "display_name":    user.get("displayName", ""),
                        "role":            entry.get("role", {}).get("name", "Member"),
                    })
            cursor = data.get("nextPageCursor")
            if not cursor:
                break
            await asyncio.sleep(0.5)
        logger.info(f"fetched {len(members)} members from group {group_id}")
        return members

    async def get_user_id_by_username(self, username: str) -> int | None:
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
            ) as resp:
                if resp.status == 200:
                    data  = await resp.json()
                    users = data.get("data", [])
                    if users:
                        user_id = users[0]["id"]
                        self._set_cache(cache_key, str(user_id))
                        return user_id
                else:
                    logger.error(f"Roblox username lookup returned {resp.status} for {username}")
        except Exception as e:
            logger.error(f"error looking up user ID for {username}: {e}")
        return None

    async def get_username_by_id(self, user_id: int) -> str | None:
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
        """fetch live profile description — never cached, needed for verification"""
        await self._ensure_session()
        try:
            async with self.session.get(
                f"https://users.roblox.com/v1/users/{user_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
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
        self.cache.clear()
        logger.info("Roblox API cache cleared")

    def get_cache_stats(self) -> dict:
        now = time.time()
        fresh = sum(
            1 for e in self.cache.values()
            if (now - e['timestamp']) < self.cache_duration
        )
        return {
            'total_entries': len(self.cache),
            'fresh_entries': fresh,
            'stale_entries': len(self.cache) - fresh,
        }
