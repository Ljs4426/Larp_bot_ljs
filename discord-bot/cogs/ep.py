import discord
from discord import app_commands
from discord.ext import commands
import os
import logging

from utils.rate_limit import RateLimiter

logger = logging.getLogger(__name__)


def _has_ep_permission(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True

    role_id = int(os.getenv('EP_MANAGER_ROLE_ID', 0))
    if not role_id:
        return interaction.user.guild_permissions.manage_guild

    ep_role = interaction.guild.get_role(role_id)
    if not ep_role:
        return False

    return any(r.position >= ep_role.position for r in interaction.user.roles)


class EP(commands.GroupCog, name="ep"):

    def __init__(self, bot: commands.Bot, database, roblox_api, command_logger):
        super().__init__()
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.rate_limiter = RateLimiter(max_uses=10, time_window=60)

    @app_commands.command(name="edit", description="Adjust a member's EP (positive or negative)")
    @app_commands.describe(
        roblox_username="The member's Roblox username",
        ep_value="Amount to add (use a negative number to subtract)"
    )
    async def ep_edit(
        self,
        interaction: discord.Interaction,
        roblox_username: str,
        ep_value: int
    ):
        await interaction.response.defer(ephemeral=True)

        if not _has_ep_permission(interaction):
            await interaction.followup.send(
                "❌ You don't have permission to edit EP. "
                "(Requires the EP Manager role or higher.)",
                ephemeral=True
            )
            await self.command_logger(
                interaction, "ep edit",
                {"roblox_username": roblox_username, "ep_value": ep_value},
                success=False, error="Permission denied"
            )
            return

        allowed, retry_after = self.rate_limiter.check_rate_limit(
            interaction.user.id, "ep-edit"
        )
        if not allowed:
            await interaction.followup.send(
                f"❌ You're using this command too quickly. "
                f"Please wait {retry_after} second(s).",
                ephemeral=True
            )
            return

        if ep_value == 0:
            await interaction.followup.send(
                "❌ EP value cannot be 0.",
                ephemeral=True
            )
            return

        record = await self.database.get_ep_record_by_username(roblox_username)

        if not record:
            roblox_user_id = await self.roblox_api.get_user_id_by_username(roblox_username)
            if roblox_user_id:
                record = await self.database.add_ep_record(
                    roblox_username=roblox_username,
                    roblox_user_id=roblox_user_id
                )
                logger.info(
                    f"Auto-created EP record for {roblox_username} "
                    f"(ID: {roblox_user_id}) during /ep edit"
                )
            else:
                await interaction.followup.send(
                    f"❌ No EP record found for **{roblox_username}** and they could not "
                    f"be resolved on Roblox. Check the username and try again.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction, "ep edit",
                    {"roblox_username": roblox_username, "ep_value": ep_value},
                    success=False, error="User not found"
                )
                return

        ep_before = record["ep"]

        updated = await self.database.update_ep(record["roblox_user_id"], ep_value)
        if not updated:
            await interaction.followup.send(
                "❌ Failed to update EP. Please try again.",
                ephemeral=True
            )
            return

        ep_after = updated["ep"]
        sign = "+" if ep_value > 0 else ""

        await interaction.followup.send(
            f"✅ EP updated for **{updated['roblox_username']}**\n"
            f"**Change:** {sign}{ep_value}\n"
            f"**EP:** {ep_before} → **{ep_after}**",
            ephemeral=True
        )

        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="EP Edited",
                color=discord.Color.green() if ep_value > 0 else discord.Color.orange()
            )
            embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
            embed.add_field(name="Member", value=updated['roblox_username'], inline=True)
            embed.add_field(name="Change", value=f"{sign}{ep_value}", inline=True)
            embed.add_field(name="New EP", value=str(ep_after), inline=True)
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send EP log embed: {e}")

        await self.command_logger(
            interaction, "ep edit",
            {"roblox_username": roblox_username, "ep_value": ep_value,
             "ep_before": ep_before, "ep_after": ep_after},
            success=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EP(bot, bot.database, bot.roblox_api, bot.command_logger))
    logger.info("EP cog loaded")
