# /log cog — screenshot OCR → confirm → award EP → post to event log

import asyncio
import base64
import io
import os
import re
import logging
from datetime import datetime, timezone
from typing import List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.events import load_events, get_ep_for_event, is_tryout_event
from utils.rate_limit import RateLimiter
from utils.validators import validate_image_attachment, ValidationError

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r'\b([A-Za-z0-9][A-Za-z0-9_]{1,18}[A-Za-z0-9]|[A-Za-z0-9]{3})\b')
_VALID_USERNAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_]{1,18}[A-Za-z0-9]$|^[A-Za-z0-9]{3}$')

_STOPWORDS = {
    'the', 'and', 'for', 'you', 'with', 'this', 'that', 'from', 'are',
    'was', 'not', 'but', 'all', 'can', 'her', 'his', 'our', 'out',
    'one', 'had', 'has', 'have', 'him', 'its', 'new', 'who', 'did',
    'get', 'has', 'way', 'use', 'say', 'she', 'may', 'day', 'see',
    'two', 'how', 'now', 'any', 'each', 'just', 'into', 'over',
    'also', 'back', 'after', 'used', 'your', 'work', 'life', 'only',
    'game', 'play', 'chat', 'team', 'kill', 'died', 'map', 'win',
}


def _has_log_permission(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    role_id = int(os.getenv('LOG_ROLE_ID', 0)) or int(os.getenv('EP_MANAGER_ROLE_ID', 0))
    if not role_id:
        return interaction.user.guild_permissions.manage_guild
    role = interaction.guild.get_role(role_id)
    if not role:
        return False
    return any(r.position >= role.position for r in interaction.user.roles)


async def event_type_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    events = load_events()
    matches = [
        app_commands.Choice(name=e["name"], value=e["name"])
        for e in events
        if current.lower() in e["name"].lower()
    ]
    return matches[:25]


def _detected_embed(event_name: str, usernames: List[str], ep_amount: int) -> discord.Embed:
    name_list = "\n".join(usernames) if usernames else "*None detected*"
    embed = discord.Embed(
        title=f"Detected Usernames — {event_name}",
        description=(
            f"**{len(usernames)}** username(s) extracted from the screenshot.\n"
            f"Each will receive **+{ep_amount} EP** on confirmation."
        ),
        color=discord.Color.blurple()
    )
    embed.add_field(name="Usernames", value=name_list[:1024], inline=False)
    return embed


def _confirmation_embed(
    event_name: str,
    usernames: List[str],
    ep_amount: int,
    passed_usernames: Optional[List[str]] = None
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Confirm EP Award — {event_name}",
        color=discord.Color.gold()
    )
    embed.add_field(
        name=f"Participants ({len(usernames)})",
        value=("\n".join(usernames) or "*None*")[:1024],
        inline=False
    )
    if passed_usernames:
        embed.add_field(
            name=f"Passed ({len(passed_usernames)})",
            value=("\n".join(passed_usernames) or "*None*")[:1024],
            inline=False
        )
    embed.add_field(name="EP per Member", value=str(ep_amount), inline=True)
    embed.add_field(name="Total Members",  value=str(len(usernames)), inline=True)
    embed.set_footer(text="Press Confirm to award EP, or Cancel to abort.")
    return embed


def _parse_edit_format(text: str) -> List[str]:
    # orig | new → rename, | new → add, orig | → remove, no pipe → keep
    result: List[str] = []
    seen: set = set()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if '|' in line:
            _, _, right = line.partition('|')
            username = right.strip()
        else:
            username = line
        if not username:          # blank right side → remove
            continue
        if not _VALID_USERNAME_RE.match(username):
            continue
        key = username.lower()
        if key not in seen:
            seen.add(key)
            result.append(username)
    return result


def _event_log_embed(
    event_name: str,
    host: discord.Member,
    usernames: List[str],
    ep_amount: int,
    screenshot_url: Optional[str],
) -> discord.Embed:
    embed = discord.Embed(
        title="📋 Event Logged",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="Event Type", value=event_name, inline=True)
    embed.add_field(name="Host", value=host.mention, inline=True)
    embed.add_field(name="Date", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)

    # split attendees into multiple fields if > 1024 chars
    if usernames:
        chunks, current = [], ""
        for line in usernames:
            if len(current) + len(line) + 1 > 1020:
                chunks.append(current.rstrip())
                current = ""
            current += line + "\n"
        if current:
            chunks.append(current.rstrip())
        embed.add_field(
            name=f"Attendees ({len(usernames)})",
            value=chunks[0],
            inline=False,
        )
        for chunk in chunks[1:]:
            embed.add_field(name="\u200b", value=chunk, inline=False)
    else:
        embed.add_field(name="Attendees", value="*None*", inline=False)

    embed.add_field(name="EP Awarded Each", value=str(ep_amount), inline=True)
    embed.add_field(name="Total EP", value=str(ep_amount * len(usernames)), inline=True)

    if screenshot_url:
        embed.set_image(url=screenshot_url)
        embed.add_field(name="SS", value="*(see image below)*", inline=False)

    return embed



class ConfirmLogView(discord.ui.View):
    def __init__(
        self,
        bot,
        database,
        command_logger,
        event_name: str,
        usernames: List[str],
        ep_amount: int,
        requester: discord.Member,
        screenshot_url: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.database = database
        self.command_logger = command_logger
        self.event_name = event_name
        self.usernames = usernames
        self.ep_amount = ep_amount
        self.requester = requester
        self.screenshot_url = screenshot_url

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        prefilled = "\n".join(f"{u} | {u}" for u in self.usernames)
        await interaction.response.send_message(
            "Use this format to edit the attendees, then **send it as a message in this channel**.\n"
            "`orig | new` — rename   `| newname` — add   `origname |` — remove\n\n"
            f"```\n{prefilled}\n```\n"
            "You have **2 minutes**. Your message will be deleted after processing.",
            ephemeral=True,
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=120)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Edit timed out — no changes made.", ephemeral=True)
            return

        try:
            await msg.delete()
        except Exception:
            pass

        final = _parse_edit_format(msg.content)
        embed = _confirmation_embed(self.event_name, final, self.ep_amount)
        view  = ConfirmLogView(
            self.bot, self.database, self.command_logger,
            self.event_name, final, self.ep_amount, self.requester,
            screenshot_url=self.screenshot_url,
        )
        await interaction.followup.send(
            "✅ List updated — use the buttons below to confirm or cancel.",
            embed=embed, view=view, ephemeral=True,
        )

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        awarded: List[str] = []
        not_found: List[str] = []

        for username in self.usernames:
            updated = await self.database.update_ep_by_username(username, self.ep_amount)
            if updated:
                awarded.append(f"{username} → {updated['ep']} EP")
            else:
                not_found.append(username)

        lines = [f"✅ Awarded **+{self.ep_amount} EP** to **{len(awarded)}** member(s)."]
        if awarded:
            lines.append("**Updated:**\n" + "\n".join(awarded[:20]))
        if not_found:
            lines.append(
                f"⚠️ **{len(not_found)}** username(s) not in EP records:\n"
                + ", ".join(not_found[:20])
            )
        await interaction.followup.send("\n\n".join(lines), ephemeral=True)

        awarded_names = [u.split(" →")[0] for u in awarded]
        await self.database.add_event_log_entry(
            event_type=self.event_name,
            ep_awarded=self.ep_amount,
            participants=awarded_names,
            not_found=not_found,
            host_discord_id=self.requester.id,
            host_discord_name=str(self.requester),
            screenshot_url=self.screenshot_url,
        )

        event_log_channel_id = int(os.getenv('EVENT_LOG_CHANNEL_ID', 0))
        if event_log_channel_id:
            event_log_channel = self.bot.get_channel(event_log_channel_id)
            if event_log_channel:
                try:
                    embed = _event_log_embed(
                        self.event_name,
                        self.requester,
                        awarded_names,
                        self.ep_amount,
                        self.screenshot_url,
                    )
                    await event_log_channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send event log embed: {e}")

        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title=f"Event Logged — {self.event_name}",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Logged by",       value=self.requester.mention, inline=True)
            embed.add_field(name="EP Awarded",      value=str(self.ep_amount),    inline=True)
            embed.add_field(name="Members Awarded", value=str(len(awarded)),      inline=True)
            if not_found:
                embed.add_field(
                    name="Not Found",
                    value=", ".join(not_found[:20]),
                    inline=False
                )
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send log embed: {e}")

        logger.info(
            f"/log {self.event_name}: +{self.ep_amount} EP to "
            f"{len(awarded)} members; {len(not_found)} not found"
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ EP award cancelled.", ephemeral=True)


class PassedUsersModal(discord.ui.Modal, title="Enter Passed Usernames"):
    usernames_input = discord.ui.TextInput(
        label="Passed Usernames (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="username1\nusername2\nusername3",
        required=True,
        max_length=2000
    )

    def __init__(
        self,
        bot,
        database,
        command_logger,
        event_name: str,
        detected_usernames: List[str],
        ep_amount: int,
        requester: discord.Member,
        screenshot_url: Optional[str] = None,
    ):
        super().__init__()
        self.bot = bot
        self.database = database
        self.command_logger = command_logger
        self.event_name = event_name
        self.detected_usernames = detected_usernames
        self.ep_amount = ep_amount
        self.requester = requester
        self.screenshot_url = screenshot_url

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.usernames_input.value.strip().split('\n')
        passed = [u.strip() for u in raw if u.strip()]
        passed = [u for u in passed if _USERNAME_RE.match(u)]

        seen: set = {u.lower() for u in self.detected_usernames}
        merged = list(self.detected_usernames)
        for u in passed:
            if u.lower() not in seen:
                merged.append(u)
                seen.add(u.lower())

        view = ConfirmLogView(
            self.bot, self.database, self.command_logger,
            self.event_name, merged, self.ep_amount, self.requester,
            screenshot_url=self.screenshot_url,
        )
        embed = _confirmation_embed(self.event_name, merged, self.ep_amount, passed_usernames=passed)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TryoutInputView(discord.ui.View):
    def __init__(
        self,
        bot,
        database,
        command_logger,
        event_name: str,
        detected_usernames: List[str],
        ep_amount: int,
        requester: discord.Member,
        screenshot_url: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.database = database
        self.command_logger = command_logger
        self.event_name = event_name
        self.detected_usernames = detected_usernames
        self.ep_amount = ep_amount
        self.requester = requester
        self.screenshot_url = screenshot_url

    @discord.ui.button(label="✏️ Edit Attendees", style=discord.ButtonStyle.secondary)
    async def edit_attendees(self, interaction: discord.Interaction, button: discord.ui.Button):
        prefilled = "\n".join(f"{u} | {u}" for u in self.detected_usernames)
        await interaction.response.send_message(
            "COPY this format to edit the attendees, then **send it as a message in this channel**.\n"
            "`orig | new` — rename   `| newname` — add   `origname |` — remove\n\n"
            f"```\n{prefilled}\n```\n"
            "You have **2 minutes**. Your message will be deleted after processing.",
            ephemeral=True,
        )

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await interaction.client.wait_for('message', check=check, timeout=120)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Edit timed out — no changes made.", ephemeral=True)
            return

        try:
            await msg.delete()
        except Exception:
            pass

        final = _parse_edit_format(msg.content)
        self.detected_usernames = final
        embed = _confirmation_embed(self.event_name, final, self.ep_amount)
        view  = ConfirmLogView(
            self.bot, self.database, self.command_logger,
            self.event_name, final, self.ep_amount, self.requester,
            screenshot_url=self.screenshot_url,
        )
        await interaction.followup.send(
            "✅ List updated — use the buttons below to confirm or cancel.",
            embed=embed, view=view, ephemeral=True,
        )

    @discord.ui.button(label="📝 Enter Passed Usernames", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PassedUsersModal(
            self.bot, self.database, self.command_logger,
            self.event_name, self.detected_usernames, self.ep_amount, self.requester,
            screenshot_url=self.screenshot_url,
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="⏭️ Skip (Award All)", style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        view = ConfirmLogView(
            self.bot, self.database, self.command_logger,
            self.event_name, self.detected_usernames, self.ep_amount, self.requester,
            screenshot_url=self.screenshot_url,
        )
        embed = _confirmation_embed(self.event_name, self.detected_usernames, self.ep_amount)
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class Log(commands.Cog):
    def __init__(self, bot: commands.Bot, database, roblox_api, command_logger):
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.rate_limiter = RateLimiter(max_uses=5, time_window=60)

    @app_commands.command(name="log", description="Log an event and award EP to participants")
    @app_commands.describe(
        event_type="Type of event (choose from the list)",
        screenshot="Screenshot proof of the event (PNG, JPG, GIF, WebP — max 10 MB)"
    )
    @app_commands.autocomplete(event_type=event_type_autocomplete)
    async def log_event(
        self,
        interaction: discord.Interaction,
        event_type: str,
        screenshot: discord.Attachment
    ):
        if not _has_log_permission(interaction):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
            return

        allowed, retry_after = self.rate_limiter.check_rate_limit(interaction.user.id, "log")
        if not allowed:
            await interaction.response.send_message(
                f"❌ Please wait {retry_after} second(s) before using this again.",
                ephemeral=True
            )
            return

        ep_amount = get_ep_for_event(event_type)
        if ep_amount is None:
            event_names = ", ".join(e["name"] for e in load_events()) or "none configured"
            await interaction.response.send_message(
                f"❌ Unknown event type **{event_type}**.\nValid types: {event_names}",
                ephemeral=True
            )
            return

        try:
            validate_image_attachment(screenshot)
        except ValidationError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        image_bytes = await self._download_image(screenshot.url)
        if not image_bytes:
            await interaction.followup.send(
                "❌ Failed to download the screenshot. Please try again.",
                ephemeral=True
            )
            return

        content_type = screenshot.content_type or "image/png"
        usernames = await self._extract_usernames(image_bytes, content_type)
        screenshot_url = screenshot.url

        if is_tryout_event(event_type):
            embed = _detected_embed(event_type, usernames, ep_amount)
            embed.set_footer(
                text="Click 'Enter Passed Usernames' to add passers, or 'Skip' to award all detected."
            )
            view = TryoutInputView(
                self.bot, self.database, self.command_logger,
                event_type, usernames, ep_amount, interaction.user,
                screenshot_url=screenshot_url,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            embed = _confirmation_embed(event_type, usernames, ep_amount)
            view = ConfirmLogView(
                self.bot, self.database, self.command_logger,
                event_type, usernames, ep_amount, interaction.user,
                screenshot_url=screenshot_url,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        await self.command_logger(
            interaction, "log",
            {"event_type": event_type, "usernames_detected": len(usernames)},
            success=True
        )


    async def _download_image(self, url: str) -> Optional[bytes]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
        return None

    async def _extract_usernames(self, image_bytes: bytes, content_type: str) -> List[str]:
        usernames = await self._extract_with_ocr(image_bytes)
        if not usernames:
            logger.info("OCR found no usernames — falling back to Claude API")
            usernames = await self._extract_with_claude(image_bytes, content_type)
        return usernames

    async def _extract_with_ocr(self, image_bytes: bytes) -> List[str]:
        try:
            import pytesseract
            from PIL import Image, ImageEnhance

            def _run_ocr(data: bytes) -> str:
                img = Image.open(io.BytesIO(data)).convert('L')
                img = ImageEnhance.Contrast(img).enhance(2.0)
                return pytesseract.image_to_string(img)

            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, _run_ocr, image_bytes)

            raw = _USERNAME_RE.findall(text)
            seen: set = set()
            result: List[str] = []
            for u in raw:
                if u.lower() not in _STOPWORDS and u.lower() not in seen:
                    seen.add(u.lower())
                    result.append(u)
            return result

        except ImportError:
            logger.info("pytesseract not installed — skipping OCR")
            return []
        except Exception as e:
            logger.error(f"OCR extraction error: {e}")
            return []

    async def _extract_with_claude(self, image_bytes: bytes, content_type: str) -> List[str]:
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return []
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-6')
            media_type = content_type if content_type.startswith("image/") else "image/png"
            image_data = base64.standard_b64encode(image_bytes).decode("utf-8")

            message = await client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": image_data},
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a screenshot from a Roblox game. "
                                "Extract all visible Roblox usernames. "
                                "Roblox usernames: 3-20 chars, letters/numbers/underscores only. "
                                "Return ONLY the usernames, one per line, no extra text."
                            )
                        }
                    ],
                }],
            )

            raw_text = message.content[0].text.strip()
            valid_re = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_]{1,18}[A-Za-z0-9]$|^[A-Za-z0-9]{3}$')
            seen: set = set()
            result: List[str] = []
            for line in raw_text.split('\n'):
                u = line.strip()
                if valid_re.match(u) and u.lower() not in _STOPWORDS and u.lower() not in seen:
                    seen.add(u.lower())
                    result.append(u)
            return result

        except Exception as e:
            logger.error(f"Claude API extraction error: {e}", exc_info=True)
            return []


async def setup(bot: commands.Bot):
    await bot.add_cog(Log(bot, bot.database, bot.roblox_api, bot.command_logger))
    logger.info("Log cog loaded")
