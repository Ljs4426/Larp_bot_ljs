"""Backup channel & bot status management cog.

Behaviour
---------
On startup (on_ready):
  - Hide all BACKUP_CHANNEL_IDS by denying @everyone view_channel.
  - Send a "Bot Online" embed to STATUS_CHANNEL_ID.

On shutdown (SIGTERM, SIGINT, or bot.close()):
  - Unhide all BACKUP_CHANNEL_IDS so members can use them manually.
  - Send a "Bot Offline" embed to STATUS_CHANNEL_ID.

The go_offline() method is public so main.py can call it from close()
before the WebSocket connection closes.

Environment variables
---------------------
STATUS_CHANNEL_ID   — channel for online/offline status embeds
BACKUP_CHANNEL_IDS  — comma-separated list of channel IDs to hide/unhide
ROBLOX_USER_ID      — used for embed footer avatar (existing var)
ROBLOX_GROUP_ID     — used for embed thumbnail (existing var)
"""

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone
from typing import List

import discord
from discord.ext import commands

from utils.embeds import get_footer_text, get_embed_color

logger = logging.getLogger(__name__)


class Backup(commands.Cog):
    """Handles backup channel visibility and bot status notifications."""

    def __init__(self, bot: commands.Bot, roblox_api):
        self.bot = bot
        self.roblox_api = roblox_api
        self._online = False  # Guard against double-offline calls

    # ---------------------------------------------------------------- #
    # Public lifecycle methods (called by main.py as well)             #
    # ---------------------------------------------------------------- #

    async def go_online(self):
        """Hide backup channels and post the online embed."""
        if self._online:
            return
        self._online = True

        await self._set_backup_channel_visibility(visible=False)
        await self._send_status_embed(online=True)
        logger.info("Backup cog: bot marked online — backup channels hidden")

    async def go_offline(self):
        """Unhide backup channels and post the offline embed."""
        if not self._online:
            return  # Already offline — don't double-post
        self._online = False

        await self._send_status_embed(online=False)
        await self._set_backup_channel_visibility(visible=True)
        logger.info("Backup cog: bot marked offline — backup channels visible")

    # ---------------------------------------------------------------- #
    # Discord event listeners                                           #
    # ---------------------------------------------------------------- #

    @commands.Cog.listener()
    async def on_ready(self):
        """Run startup sequence once when the bot first becomes ready."""
        if not self._online:
            await self.go_online()

    # ---------------------------------------------------------------- #
    # Internal helpers                                                   #
    # ---------------------------------------------------------------- #

    def _get_backup_channel_ids(self) -> List[int]:
        raw = os.getenv('BACKUP_CHANNEL_IDS', '')
        ids = []
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def _get_status_channel_id(self) -> int:
        return int(os.getenv('STATUS_CHANNEL_ID', 0))

    async def _set_backup_channel_visibility(self, visible: bool):
        """
        Set @everyone view_channel permission on every backup channel.

        visible=True  → unhide (bot going offline)
        visible=False → hide   (bot going online)
        """
        backup_ids = self._get_backup_channel_ids()
        if not backup_ids:
            logger.warning(
                "Backup cog: BACKUP_CHANNEL_IDS is empty — "
                "no channels to show/hide"
            )
            return

        action = "Unhiding" if visible else "Hiding"
        reason = (
            "Bot went offline — backup channels now visible"
            if visible
            else "Bot came online — backup channels hidden"
        )

        for guild in self.bot.guilds:
            for channel_id in backup_ids:
                channel = guild.get_channel(channel_id)
                if not channel:
                    logger.warning(
                        f"Backup cog: channel {channel_id} not found in guild '{guild.name}'"
                    )
                    continue
                try:
                    await channel.set_permissions(
                        guild.default_role,
                        view_channel=visible,
                        reason=reason
                    )
                    logger.info(
                        f"Backup cog: {action} #{channel.name} in '{guild.name}'"
                    )
                except discord.Forbidden:
                    logger.error(
                        f"Backup cog: Missing permissions to modify #{channel.name} "
                        f"(ID {channel_id}) in '{guild.name}'"
                    )
                except discord.HTTPException as e:
                    logger.error(
                        f"Backup cog: HTTP error modifying channel {channel_id}: {e}"
                    )

    async def _send_status_embed(self, online: bool):
        """Post a status embed to the configured STATUS_CHANNEL_ID."""
        status_channel_id = self._get_status_channel_id()
        if not status_channel_id:
            logger.warning("Backup cog: STATUS_CHANNEL_ID not set — skipping status embed")
            return

        channel = self.bot.get_channel(status_channel_id)
        if not channel:
            logger.warning(
                f"Backup cog: STATUS_CHANNEL_ID {status_channel_id} not found"
            )
            return

        # Fetch Roblox assets to match the existing embed style
        roblox_user_id  = 296030103
        roblox_group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))

        footer_icon_url = None
        group_icon_url  = None
        try:
            footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
            group_icon_url  = await self.roblox_api.get_group_icon(roblox_group_id)
        except Exception as e:
            logger.warning(f"Backup cog: could not fetch Roblox assets for embed: {e}")

        if online:
            embed = discord.Embed(
                title="🟢 Bot Online",
                description=(
                    "The **327th Star Corps** bot is online and fully operational.\n"
                    "Backup channels have been hidden."
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
        else:
            backup_ids   = self._get_backup_channel_ids()
            channel_mentions = " ".join(f"<#{cid}>" for cid in backup_ids) or "*none configured*"
            embed = discord.Embed(
                title="🔴 Bot Offline",
                description=(
                    "The **327th Star Corps** bot has gone offline.\n"
                    f"The following backup channel(s) are now visible for manual submissions:\n"
                    f"{channel_mentions}"
                ),
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )

        if group_icon_url:
            embed.set_thumbnail(url=group_icon_url)

        embed.set_footer(
            text=get_footer_text(),
            icon_url=footer_icon_url
        )

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("Backup cog: Missing permissions to send to STATUS_CHANNEL_ID")
        except Exception as e:
            logger.error(f"Backup cog: Failed to send status embed: {e}")


async def setup(bot: commands.Bot):
    """Load Backup cog."""
    await bot.add_cog(Backup(bot, bot.roblox_api))
    logger.info("Backup cog loaded")
