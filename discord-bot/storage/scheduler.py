"""Scheduled tasks."""

import asyncio
import io
import os
import logging
from datetime import datetime, timedelta, timezone

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from utils.week import current_week_start
from utils.sheets import sync_ep_to_sheet, sync_events_to_sheet

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, bot: discord.Client, database):
        self.bot = bot
        self.database = database
        self.scheduler = AsyncIOScheduler()

    def start(self):
        ep_sync_hours = int(os.getenv('EP_SYNC_INTERVAL_HOURS', 6))

        self.scheduler.add_job(
            self.check_expired_inactivity,
            IntervalTrigger(hours=1),
            id='check_expired_inactivity', replace_existing=True
        )
        self.scheduler.add_job(
            self.check_expired_cooldowns,
            IntervalTrigger(hours=1),
            id='check_expired_cooldowns', replace_existing=True
        )
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(hour=3, minute=0),
            id='cleanup_old_data', replace_existing=True
        )
        self.scheduler.add_job(
            self.cleanup_rate_limiter,
            IntervalTrigger(hours=6),
            id='cleanup_rate_limiter', replace_existing=True
        )
        self.scheduler.add_job(
            self.cleanup_expired_verifications,
            IntervalTrigger(minutes=15),
            id='cleanup_expired_verifications', replace_existing=True
        )
        self.scheduler.add_job(
            self.sync_ep_records,
            IntervalTrigger(hours=ep_sync_hours),
            id='sync_ep_records', replace_existing=True
        )

        if os.getenv('ENABLE_REPORT', 'true').lower() == 'true':
            self.scheduler.add_job(
                self.generate_weekly_report,
                CronTrigger(day_of_week='sun', hour=19, minute=0, timezone='UTC'),
                id='weekly_report', replace_existing=True
            )

        if os.getenv('ENABLE_SHEETS', 'false').lower() == 'true':
            sheets_hours = int(os.getenv('SHEETS_SYNC_INTERVAL_HOURS', ep_sync_hours))
            self.scheduler.add_job(
                self.sync_sheets,
                IntervalTrigger(hours=sheets_hours),
                id='sync_sheets', replace_existing=True
            )

        self.scheduler.start()
        logger.info("scheduler started")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("scheduler stopped")

    async def check_expired_inactivity(self):
        try:
            expired = await self.database.get_expired_inactivity_notices()
            if not expired:
                return

            inactivity_role_id = int(os.getenv('INACTIVITY_ROLE_ID', 0))
            cooldown_role_id   = int(os.getenv('INACTIVITY_COOLDOWN_ROLE_ID', 0))

            for notice in expired:
                user_id = notice['user_id']

                guild  = None
                member = None
                for g in self.bot.guilds:
                    member = g.get_member(user_id)
                    if member:
                        guild = g
                        break

                if not guild or not member:
                    logger.warning(f"member {user_id} not found for inactivity expiry")
                    await self.database.update_inactivity_status(notice['message_id'], 'expired', 0)
                    continue

                try:
                    inactivity_role = guild.get_role(inactivity_role_id)
                    if inactivity_role and inactivity_role in member.roles:
                        await member.remove_roles(inactivity_role, reason="inactivity ended")

                    cooldown_role = guild.get_role(cooldown_role_id)
                    if cooldown_role:
                        await member.add_roles(cooldown_role, reason="inactivity cooldown")
                        cooldown_end = datetime.now(timezone.utc) + timedelta(days=14)
                        await self.database.add_cooldown(user_id, cooldown_end)

                    inactivity_channel_id = int(os.getenv('INACTIVITY_CHANNEL_ID', 0))
                    inactivity_channel = guild.get_channel(inactivity_channel_id)
                    if inactivity_channel:
                        try:
                            msg = await inactivity_channel.fetch_message(notice['message_id'])
                            await msg.delete()
                        except discord.NotFound:
                            pass
                        except Exception as e:
                            logger.error(f"error deleting inactivity msg: {e}")

                    try:
                        await member.send(
                            "Your inactivity period has ended. You now have a 14-day cooldown "
                            "before you can request another inactivity notice."
                        )
                    except discord.Forbidden:
                        pass

                    await self.database.update_inactivity_status(notice['message_id'], 'expired', 0)

                except discord.Forbidden:
                    logger.error(f"missing perms to manage roles for {member}")
                except Exception as e:
                    logger.error(f"error processing expired inactivity for {user_id}: {e}")

            logger.info(f"processed {len(expired)} expired inactivity notices")

        except Exception as e:
            logger.error(f"check_expired_inactivity error: {e}")

    async def check_expired_cooldowns(self):
        try:
            expired = await self.database.get_expired_cooldowns()
            if not expired:
                return

            cooldown_role_id = int(os.getenv('INACTIVITY_COOLDOWN_ROLE_ID', 0))

            for cooldown in expired:
                user_id = cooldown['user_id']

                guild  = None
                member = None
                for g in self.bot.guilds:
                    member = g.get_member(user_id)
                    if member:
                        guild = g
                        break

                if not guild or not member:
                    logger.warning(f"member {user_id} not found for cooldown removal")
                    await self.database.remove_cooldown(user_id)
                    continue

                try:
                    cooldown_role = guild.get_role(cooldown_role_id)
                    if cooldown_role and cooldown_role in member.roles:
                        await member.remove_roles(cooldown_role, reason="cooldown ended")

                    await self.database.remove_cooldown(user_id)

                    try:
                        await member.send("Your inactivity cooldown has ended. You can now request inactivity notices again.")
                    except discord.Forbidden:
                        pass

                except discord.Forbidden:
                    logger.error(f"missing perms to remove cooldown role from {member}")
                except Exception as e:
                    logger.error(f"error removing cooldown for {user_id}: {e}")

            logger.info(f"processed {len(expired)} expired cooldowns")

        except Exception as e:
            logger.error(f"check_expired_cooldowns error: {e}")

    async def cleanup_old_data(self):
        try:
            await self.database.cleanup_old_data(days=90)
        except Exception as e:
            logger.error(f"cleanup_old_data error: {e}")

    async def cleanup_expired_verifications(self):
        try:
            await self.database.cleanup_expired_verifications()
        except Exception as e:
            logger.error(f"cleanup_expired_verifications error: {e}")

    async def cleanup_rate_limiter(self):
        try:
            for cog in self.bot.cogs.values():
                if hasattr(cog, 'rate_limiter'):
                    cog.rate_limiter.cleanup_old_entries()
        except Exception as e:
            logger.error(f"cleanup_rate_limiter error: {e}")

    async def sync_ep_records(self):
        try:
            group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))
            members  = await self.bot.roblox_api.get_group_members(group_id)
            if not members:
                logger.warning("EP sync: roblox returned no members, skipping")
                return

            added, removed = await self.database.sync_ep_records(members)
            if not added and not removed:
                return

            log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
            log_channel    = self.bot.get_channel(log_channel_id)

            if log_channel:
                if added:
                    names    = "\n".join(r["roblox_username"] for r in added[:25])
                    overflow = len(added) - 25
                    if overflow > 0:
                        names += f"\n… and {overflow} more"
                    embed = discord.Embed(
                        title="EP Sync — Members Added",
                        description=f"**{len(added)}** new member(s) added to EP records.",
                        color=discord.Color.green(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name="New Members", value=names or "—", inline=False)
                    await log_channel.send(embed=embed)

                if removed:
                    names    = "\n".join(f"{r['roblox_username']} (EP: {r['ep']})" for r in removed[:25])
                    overflow = len(removed) - 25
                    if overflow > 0:
                        names += f"\n… and {overflow} more"
                    embed = discord.Embed(
                        title="EP Sync — Members Removed",
                        description=f"**{len(removed)}** member(s) removed from EP records (left group).",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name="Removed Members", value=names or "—", inline=False)
                    await log_channel.send(embed=embed)

            logger.info(f"EP sync: +{len(added)} added, -{len(removed)} removed")

        except Exception as e:
            logger.error(f"sync_ep_records error: {e}", exc_info=True)

    async def sync_sheets(self):
        try:
            ep_records = await self.database.get_all_ep_records()
            ok = await sync_ep_to_sheet(ep_records)
            if not ok:
                logger.warning("sheets EP sync returned False — check GOOGLE_SHEETS_CREDS_FILE / GOOGLE_SHEET_ID")

            # also sync the event log to its own tab
            events = await self.database.get_all_event_log_entries()
            ok2 = await sync_events_to_sheet(events)
            if not ok2:
                logger.warning("sheets event sync returned False")
        except Exception as e:
            logger.error(f"sync_sheets error: {e}")

    async def generate_weekly_report(self):
        """auto-generate and post the weekly report every sunday 19:00 utc"""
        try:
            report_channel_id = int(os.getenv('REPORT_CHANNEL_ID', 0))
            if not report_channel_id:
                return

            channel = self.bot.get_channel(report_channel_id)
            if not channel:
                logger.error(f"auto-report: channel {report_channel_id} not found")
                return

            now        = datetime.now(timezone.utc)
            week_end   = now
            week_start = current_week_start(now - timedelta(weeks=1))
            prev_start = current_week_start(now - timedelta(weeks=2))

            events      = await self.database.get_events_in_range(week_start, week_end)
            prev_events = await self.database.get_events_in_range(prev_start, week_start)
            ep_records  = await self.database.get_all_ep_records()

            if not events:
                await channel.send(
                    "📊 **Weekly Report** — No events were logged this week. "
                    "No report generated."
                )
                return

            from utils.report_builder import build_report_docx, generate_ai_summary
            from utils.week import format_week_range

            ai_summary = await generate_ai_summary(events, ep_records, days=7, prev_events=prev_events)

            config = {
                'unit_name':     os.getenv('REPORT_UNIT_NAME',    '327th Star Corps'),
                'top_ep_count':  os.getenv('REPORT_TOP_EP_COUNT', '10'),
                'days':          7,
                'color_primary': os.getenv('REPORT_COLOR_PRIMARY', '1B2A4A'),
                'color_accent':  os.getenv('REPORT_COLOR_ACCENT',  'C9A84C'),
            }

            period_str = format_week_range(week_start)
            title      = f"{config['unit_name']} — Weekly Report"

            loop       = asyncio.get_event_loop()
            docx_bytes = await loop.run_in_executor(
                None,
                build_report_docx,
                title, period_str, events, ep_records, ai_summary, config, prev_events,
            )

            filename = f"weekly_report_{week_end.strftime('%Y%m%d')}.docx"
            file     = discord.File(io.BytesIO(docx_bytes), filename=filename)

            total_ep = sum(e['ep_awarded'] * len(e['participants']) for e in events)
            embed = discord.Embed(
                title="📊  Weekly Report",
                description=f"Auto-generated report for **{period_str}**.",
                color=discord.Color.blurple(),
                timestamp=now,
            )
            embed.add_field(name="Events Logged", value=str(len(events)), inline=True)
            embed.add_field(name="EP Awarded",    value=str(total_ep),    inline=True)
            embed.set_footer(text=config['unit_name'])

            await channel.send(embed=embed, file=file)
            logger.info(f"auto-report posted: {len(events)} events, {period_str}")

        except Exception as e:
            logger.error(f"auto-report failed: {e}", exc_info=True)
