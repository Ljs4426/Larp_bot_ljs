"""Weekly activity report cog — /gen-report.

week: sunday 19:00 utc → next sunday 19:00 utc
rate limit: 2 uses per user per week
permissions: REPORT_ROLE_ID → EP_MANAGER_ROLE_ID → manage_guild → admin
"""

import asyncio
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.week import (
    current_week_start,
    current_week_end,
    format_week_range,
    week_start_for_date,
)
from utils.report_builder import build_report_docx, generate_ai_summary

logger = logging.getLogger(__name__)

_REPORT_LIMIT_PER_WEEK = 2


# ------------------------------------------------------------------ #
# Permission helper                                                    #
# ------------------------------------------------------------------ #

def _has_report_permission(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    role_id = (
        int(os.getenv('REPORT_ROLE_ID', 0))
        or int(os.getenv('EP_MANAGER_ROLE_ID', 0))
    )
    if not role_id:
        return interaction.user.guild_permissions.manage_guild
    role = interaction.guild.get_role(role_id)
    if not role:
        return False
    return any(r.position >= role.position for r in interaction.user.roles)


# ------------------------------------------------------------------ #
# Cog                                                                  #
# ------------------------------------------------------------------ #

class Report(commands.Cog):

    def __init__(self, bot: commands.Bot, database):
        self.bot = bot
        self.database = database

    @app_commands.command(
        name="gen-report",
        description="Generate a weekly activity report as a Word document"
    )
    @app_commands.describe(
        week_of="Date in the target week — YYYY-MM-DD (default: current week)",
        title="Custom report title (optional)",
    )
    async def gen_report(
        self,
        interaction: discord.Interaction,
        week_of: Optional[str] = None,
        title: Optional[str] = None,
    ):
        if not _has_report_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to generate reports.",
                ephemeral=True,
            )
            return

        # ── Validate week_of ─────────────────────────────────────────
        if week_of:
            try:
                ws = week_start_for_date(week_of)
            except ValueError:
                await interaction.response.send_message(
                    "❌ Invalid date format. Use `YYYY-MM-DD` (e.g. `2026-03-03`).",
                    ephemeral=True,
                )
                return
        else:
            ws = current_week_start()

        we = ws + timedelta(weeks=1)

        # ── Rate limit (2 per user per current week) ─────────────────
        this_week_start = current_week_start()
        usage = await self.database.get_report_usage_count(
            interaction.user.id, this_week_start
        )
        if usage >= _REPORT_LIMIT_PER_WEEK:
            reset_ts = int((this_week_start + timedelta(weeks=1)).timestamp())
            await interaction.response.send_message(
                f"❌ You've used your report quota ({_REPORT_LIMIT_PER_WEEK}/week).\n"
                f"Quota resets <t:{reset_ts}:R>.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        events      = await self.database.get_events_in_range(ws, we)
        prev_events = await self.database.get_events_in_range(ws - timedelta(weeks=1), ws)
        ep_records  = await self.database.get_all_ep_records()

        if not events:
            await interaction.followup.send(
                f"❌ No events were logged during the week of **{format_week_range(ws)}**. "
                "No report can be generated for this period.",
                ephemeral=True,
            )
            return

        # record usage after confirming data exists (don't burn quota on empty weeks)
        await self.database.add_report_usage(interaction.user.id)

        report_title = title or "Division Activity Report"
        period_str   = format_week_range(ws)

        ai_summary = await generate_ai_summary(events, ep_records, days=7, prev_events=prev_events)

        config = {
            'unit_name':     os.getenv('REPORT_UNIT_NAME',    '327th Star Corps'),
            'top_ep_count':  os.getenv('REPORT_TOP_EP_COUNT', '10'),
            'days':          7,
            'color_primary': os.getenv('REPORT_COLOR_PRIMARY', '1B2A4A'),
            'color_accent':  os.getenv('REPORT_COLOR_ACCENT',  'C9A84C'),
        }

        try:
            loop = asyncio.get_event_loop()
            docx_bytes = await loop.run_in_executor(
                None,
                build_report_docx,
                report_title, period_str, events, ep_records, ai_summary, config, prev_events,
            )
        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ Failed to generate report. Check bot logs.",
                ephemeral=True,
            )
            return

        filename = f"report_{ws.strftime('%Y%m%d')}.docx"
        file     = discord.File(io.BytesIO(docx_bytes), filename=filename)

        total_ep = sum(e['ep_awarded'] * len(e['participants']) for e in events)
        remaining = _REPORT_LIMIT_PER_WEEK - usage - 1  # -1 because we just used one

        embed = discord.Embed(
            title=f"📊  {report_title}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Period",        value=period_str,       inline=True)
        embed.add_field(name="Events Logged", value=str(len(events)), inline=True)
        embed.add_field(name="EP Awarded",    value=str(total_ep),    inline=True)
        embed.set_footer(
            text=(
                f"Generated by {interaction.user}  •  "
                f"{config['unit_name']}  •  "
                f"{remaining} report use(s) remaining this week"
            )
        )

        await interaction.followup.send(embed=embed, file=file)
        logger.info(
            f"/gen-report by {interaction.user}: {len(events)} events, "
            f"week={format_week_range(ws)}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Report(bot, bot.database))
    logger.info("Report cog loaded")
