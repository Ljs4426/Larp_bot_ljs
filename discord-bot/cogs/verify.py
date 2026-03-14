import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import os
import logging

logger = logging.getLogger(__name__)

_DEFAULT_FORMAT = "{username} | {timezone}"


def _build_nick(username: str, tz: str) -> str:
    fmt = os.getenv("NICKNAME_FORMAT", _DEFAULT_FORMAT)
    return fmt.format(username=username, timezone=tz.upper())


class Verify(commands.Cog):

    def __init__(self, bot: commands.Bot, database, command_logger):
        self.bot = bot
        self.database = database
        self.command_logger = command_logger

    @app_commands.command(name="verify", description="Link your Roblox account to Discord")
    @app_commands.describe(
        roblox_username="Your Roblox username",
        timezone="Your timezone abbreviation (e.g. EST, PST, GMT, BST)",
    )
    async def verify(self, interaction: discord.Interaction, roblox_username: str, timezone: str):
        await interaction.response.defer(ephemeral=True)

        record = await self.database.get_ep_record_by_username(roblox_username)

        if not record:
            await interaction.followup.send(
                f"❌ **{roblox_username}** isn't in the roster. Contact a staff member if you think this is wrong.",
                ephemeral=True,
            )
            await self.command_logger(
                interaction, "verify",
                {"roblox_username": roblox_username, "timezone": timezone},
                success=False, error="not in roster"
            )
            return

        existing_discord_id = record.get("discord_user_id")
        if existing_discord_id and existing_discord_id != interaction.user.id:
            await interaction.followup.send(
                "❌ That Roblox account is already linked to a different Discord account.",
                ephemeral=True,
            )
            await self.command_logger(
                interaction, "verify",
                {"roblox_username": roblox_username, "timezone": timezone},
                success=False, error="already linked to another account"
            )
            return

        if existing_discord_id == interaction.user.id:
            nick = _build_nick(roblox_username, timezone)
            try:
                await interaction.user.edit(nick=nick)
            except discord.Forbidden:
                pass
            await interaction.followup.send(
                f"✅ Already verified as **{roblox_username}** — nickname updated to `{nick}`.",
                ephemeral=True,
            )
            return

        # link discord id
        await self.database.update_ep_record(
            record["roblox_user_id"],
            {"discord_user_id": interaction.user.id}
        )

        # assign verified role if set
        role_id = int(os.getenv("VERIFIED_ROLE_ID", 0))
        role = interaction.guild.get_role(role_id) if role_id else None
        role_note = ""
        if role:
            try:
                await interaction.user.add_roles(role)
                role_note = f" and given the **{role.name}** role"
            except discord.Forbidden:
                logger.warning(f"missing perms to assign verified role {role_id}")

        # set nickname
        nick = _build_nick(roblox_username, timezone)
        try:
            await interaction.user.edit(nick=nick)
        except discord.Forbidden:
            logger.warning(f"missing perms to set nickname for {interaction.user}")
            nick = None

        nick_note = f" Nickname set to `{nick}`." if nick else " (couldn't set nickname — check bot permissions)"

        await interaction.followup.send(
            f"✅ Verified! You're linked as **{roblox_username}**{role_note}.{nick_note}",
            ephemeral=True,
        )
        logger.info(f"verified {interaction.user} as {roblox_username} [{timezone.upper()}]")

        # post to log channel
        log_channel_id = int(os.getenv("LOG_CHANNEL_ID", 0))
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Member Verified",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Discord",         value=interaction.user.mention,  inline=True)
            embed.add_field(name="Roblox Username", value=roblox_username,           inline=True)
            embed.add_field(name="Timezone",        value=timezone.upper(),          inline=True)
            if nick:
                embed.add_field(name="Nickname Set", value=f"`{nick}`", inline=False)
            if role:
                embed.add_field(name="Role Assigned", value=role.mention, inline=False)
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to send verify log: {e}")

        await self.command_logger(
            interaction, "verify",
            {"roblox_username": roblox_username, "timezone": timezone, "nickname": nick or "not set"},
            success=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot, bot.database, bot.command_logger))
    logger.info("Verify cog loaded")
