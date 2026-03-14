import discord
from discord import app_commands
from discord.ext import commands
import os
import logging

logger = logging.getLogger(__name__)

# default nick format — override with NICKNAME_FORMAT in .env
# available placeholders: {username}, {timezone}
_DEFAULT_FORMAT = "{username} | {timezone}"


def _build_nick(username: str, timezone: str) -> str:
    fmt = os.getenv("NICKNAME_FORMAT", _DEFAULT_FORMAT)
    return fmt.format(username=username, timezone=timezone.upper())


class Verify(commands.Cog):

    def __init__(self, bot: commands.Bot, database):
        self.bot = bot
        self.database = database

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
            return

        existing_discord_id = record.get("discord_user_id")
        if existing_discord_id and existing_discord_id != interaction.user.id:
            await interaction.followup.send(
                "❌ That Roblox account is already linked to a different Discord account.",
                ephemeral=True,
            )
            return

        if existing_discord_id == interaction.user.id:
            # already verified — still update the nick in case timezone changed
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


async def setup(bot: commands.Bot):
    db = bot.database
    await bot.add_cog(Verify(bot, db))
    logger.info("Verify cog loaded")
