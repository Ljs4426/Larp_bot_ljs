"""Member profile cog — /profile."""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.week import current_week_start, format_week_range

logger = logging.getLogger(__name__)


class Profile(commands.Cog):

    def __init__(self, bot: commands.Bot, database, roblox_api):
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api

    @app_commands.command(
        name="profile",
        description="View a member's Roblox profile and weekly activity"
    )
    @app_commands.describe(roblox_username="The member's Roblox username")
    async def profile(
        self,
        interaction: discord.Interaction,
        roblox_username: str,
    ):
        await interaction.response.defer()

        # ── Resolve user ─────────────────────────────────────────────
        record = await self.database.get_ep_record_by_username(roblox_username)

        if record:
            user_id = record["roblox_user_id"]
        else:
            user_id = await self.roblox_api.get_user_id_by_username(roblox_username)
            if not user_id:
                await interaction.followup.send(
                    f"❌ No profile found for **{roblox_username}**. "
                    "Make sure the Roblox username is correct.",
                    ephemeral=True,
                )
                return

        # ── Roblox avatar ─────────────────────────────────────────────
        avatar_url = await self.roblox_api.get_user_avatar(user_id)

        # ── Weekly events ─────────────────────────────────────────────
        week_start  = current_week_start()
        all_events  = await self.database.get_event_log_since(week_start)
        target_lower = roblox_username.lower()
        weekly_events = [
            e for e in all_events
            if any(p.lower() == target_lower for p in e["participants"])
        ]
        weekly_ep = sum(e["ep_awarded"] for e in weekly_events)

        # ── Leaderboard rank ──────────────────────────────────────────
        all_records = await self.database.get_all_ep_records()
        sorted_records = sorted(all_records, key=lambda r: r["ep"], reverse=True)
        rank = next(
            (i + 1 for i, r in enumerate(sorted_records)
             if r["roblox_username"].lower() == target_lower),
            None,
        )

        total_ep = record["ep"] if record else 0

        # ── Build embed ───────────────────────────────────────────────
        embed = discord.Embed(
            title=f"{roblox_username}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=avatar_url)

        embed.add_field(name="Total EP",          value=str(total_ep),        inline=True)
        embed.add_field(name="EP This Week",       value=str(weekly_ep),       inline=True)
        embed.add_field(
            name="Leaderboard Rank",
            value=f"#{rank}" if rank else "Unranked",
            inline=True,
        )

        # Events this week
        if weekly_events:
            lines = []
            for e in weekly_events:
                ts = int(datetime.fromisoformat(e["logged_at"]).timestamp())
                lines.append(f"• **{e['event_type']}** — <t:{ts}:d> (+{e['ep_awarded']} EP)")
            embed.add_field(
                name=f"Events This Week ({len(weekly_events)})",
                value="\n".join(lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="Events This Week",
                value="*No events logged this week.*",
                inline=False,
            )

        # Roblox profile link
        embed.add_field(
            name="Roblox Profile",
            value=f"[View on Roblox](https://www.roblox.com/users/{user_id}/profile)",
            inline=False,
        )

        unit = os.getenv('REPORT_UNIT_NAME', '327th Star Corps')
        embed.set_footer(
            text=f"{unit}  •  Week: {format_week_range(week_start)}"
        )

        await interaction.followup.send(embed=embed)
        logger.info(
            f"/profile {roblox_username} requested by {interaction.user} — "
            f"{len(weekly_events)} weekly events, EP={total_ep}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot, bot.database, bot.roblox_api))
    logger.info("Profile cog loaded")
