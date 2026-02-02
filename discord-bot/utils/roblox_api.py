import aiohttp
import asyncio
import time
import os
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class RobloxAPICache:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[str, Dict] = {}
        self.cache_duration = 3600  # 1 hour
        self.placeholder_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
        self.placeholder_group = "https://cdn.discordapp.com/embed/avatars/1.png"
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _is_cache_fresh(self, cache_key: str) -> bool:
        if cache_key not in self.cache:
            return False
        cache_entry = self.cache[cache_key]
        return (time.time() - cache_entry['timestamp']) < self.cache_duration

    def _get_from_cache(self, cache_key: str) -> Optional[str]:
        if self._is_cache_fresh(cache_key):
            return self.cache[cache_key]['url']
        return None

    def _set_cache(self, cache_key: str, url: str):
        self.cache[cache_key] = {
            'url': url,
            'timestamp': time.time()
        }

    async def _fetch_with_retry(self, url: str) -> Optional[dict]:
        await self._ensure_session()

        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
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
        cache_key = f"avatar_{user_id}"
        cached_url = self._get_from_cache(cache_key)
        if cached_url:
            logger.debug(f"Avatar cache hit for user {user_id}")
            return cached_url

        url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
        data = await self._fetch_with_retry(url)

        if data and 'data' in data and len(data['data']) > 0:
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                logger.info(f"Successfully fetched avatar for user {user_id}")
                return image_url

        logger.warning(f"Using placeholder avatar for user {user_id}")
        return self.placeholder_avatar

    async def get_group_icon(self, group_id: int) -> str:
        cache_key = f"group_{group_id}"
        cached_url = self._get_from_cache(cache_key)
        if cached_url:
            logger.debug(f"Group icon cache hit for group {group_id}")
            return cached_url

        url = f"https://thumbnails.roblox.com/v1/groups/icons?groupIds={group_id}&size=150x150&format=Png"
        data = await self._fetch_with_retry(url)

        if data and 'data' in data and len(data['data']) > 0:
            image_url = data['data'][0].get('imageUrl')
            if image_url:
                self._set_cache(cache_key, image_url)
                logger.info(f"Successfully fetched icon for group {group_id}")
                return image_url

        logger.warning(f"Using placeholder icon for group {group_id}")
        return self.placeholder_group

    async def get_group_members(self, group_id: int) -> list:
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

            await asyncio.sleep(0.5)

        logger.info(f"Fetched {len(members)} members from group {group_id}")
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

    def clear_cache(self):
        self.cache.clear()
        logger.info("Roblox API cache cleared")

    def get_cache_stats(self) -> dict:
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
