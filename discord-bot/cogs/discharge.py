"""Discharge command cog."""

import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from datetime import datetime, timedelta, timezone
import asyncio

from utils.validators import (
    validate_reason_length,
    ValidationError
)
from utils.rate_limit import RateLimiter
from utils.embeds import (
    create_discharge_request_embed,
    create_discharge_goodbye_embed,
    create_discharge_log_embed
)

logger = logging.getLogger(__name__)


class DischargeButtons(discord.ui.View):
    """
    Buttons for discharge request approval/denial.
    """
    
    def __init__(self, bot, database, roblox_api, command_logger, discharge_data):
        """
        Initialize buttons.
        
        Args:
            bot: Discord bot instance
            database: BotDatabase instance
            roblox_api: RobloxAPICache instance
            command_logger: Command logging function
            discharge_data: Dictionary with discharge information
        """
        super().__init__(timeout=None)  # Persistent buttons
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.discharge_data = discharge_data
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if user has permission to approve/deny.
        
        Args:
            interaction: Discord interaction
            
        Returns:
            True if user has permission
        """
        # Check for Manage Server permission
        if interaction.user.guild_permissions.manage_guild:
            return True
        
        await interaction.response.send_message(
            "❌ You don't have permission to approve/deny discharge requests. (Requires Manage Server permission)",
            ephemeral=True
        )
        return False
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="discharge_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle approve button click."""
        if not await self.check_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = self.discharge_data['user_id']
            message_id = self.discharge_data['message_id']
            reason = self.discharge_data['reason']
            
            # Get guild and member
            guild = interaction.guild
            member = guild.get_member(user_id)
            
            if not member:
                await interaction.followup.send(
                    "❌ User not found in server.",
                    ephemeral=True
                )
                return
            
            # Update database
            await self.database.update_discharge_status(
                message_id,
                'approved',
                interaction.user.id
            )
            
            # Fetch Roblox data
            roblox_user_id = int(os.getenv('ROBLOX_USER_ID', 296030103))
            roblox_group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))
            
            footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
            group_icon_url = await self.roblox_api.get_group_icon(roblox_group_id)
            
            # Send goodbye DM
            dm_sent = False
            try:
                goodbye_embed = await create_discharge_goodbye_embed(
                    group_icon_url=group_icon_url,
                    footer_icon_url=footer_icon_url
                )
                await member.send(embed=goodbye_embed)
                dm_sent = True
                logger.info(f"Sent goodbye DM to user {user_id}")
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user_id} - DMs disabled")
            except Exception as e:
                logger.error(f"Error sending goodbye DM: {e}")
            
            # Wait 2 seconds for DM to send
            if dm_sent:
                await asyncio.sleep(2)
            
            # Kick user from server
            try:
                await member.kick(reason=f"Discharge approved by {interaction.user}")
                logger.info(f"Kicked user {user_id} from server")
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I don't have permission to kick members.",
                    ephemeral=True
                )
                return
            except Exception as e:
                logger.error(f"Error kicking user: {e}")
                await interaction.followup.send(
                    f"❌ Error kicking user: {str(e)}",
                    ephemeral=True
                )
                return
            
            # Wipe EP record for the discharged user (silent if none found)
            wiped_ep = await self.database.wipe_ep_by_discord_id(user_id)
            if wiped_ep:
                logger.info(
                    f"Wiped EP record for {wiped_ep['roblox_username']} "
                    f"(Discord: {user_id}) on discharge approval"
                )

            # Send to discharge log channel
            discharge_log_channel_id = int(os.getenv('DISCHARGE_LOG_CHANNEL_ID', 0))
            discharge_log_channel = self.bot.get_channel(discharge_log_channel_id)
            
            if discharge_log_channel:
                log_embed = await create_discharge_log_embed(
                    user=member,
                    reason=reason,
                    group_icon_url=group_icon_url,
                    footer_icon_url=footer_icon_url
                )
                
                log_message = await discharge_log_channel.send(embed=log_embed)
                
                # Add reactions
                try:
                    await log_message.add_reaction("🫡")  # Salute
                    await log_message.add_reaction("🟢")  # Green circle
                    await log_message.add_reaction("🔴")  # Red circle
                except Exception as e:
                    logger.error(f"Error adding reactions to log message: {e}")
            
            # Update original embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.add_field(
                name="Status",
                value=f"✅ APPROVED by {interaction.user.mention} - User kicked",
                inline=False
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(embed=embed, view=self)
            
            await interaction.followup.send(
                f"✅ Discharge approved and user kicked from server.",
                ephemeral=True
            )
            
            logger.info(f"Discharge approved for user {user_id} by {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Error approving discharge: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while approving the discharge.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="discharge_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle deny button click."""
        if not await self.check_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = self.discharge_data['user_id']
            message_id = self.discharge_data['message_id']
            
            # Get guild and member
            guild = interaction.guild
            member = guild.get_member(user_id)
            
            if not member:
                await interaction.followup.send(
                    "❌ User not found in server.",
                    ephemeral=True
                )
                return
            
            # Update database
            await self.database.update_discharge_status(
                message_id,
                'denied',
                interaction.user.id
            )
            
            # Send DM to user
            try:
                await member.send(
                    f"Your discharge request has been denied. "
                    f"Please contact <@{interaction.user.id}> for more information."
                )
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user_id} about denied discharge")
            except Exception as e:
                logger.error(f"Error sending denial DM: {e}")
            
            # Update embed
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="Status",
                value=f"❌ DENIED by {interaction.user.mention}",
                inline=False
            )
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
            
            await interaction.message.edit(embed=embed, view=self)
            
            await interaction.followup.send(
                f"✅ Discharge denied for {member.mention}",
                ephemeral=True
            )
            
            logger.info(f"Discharge denied for user {user_id} by {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Error denying discharge: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while denying the discharge.",
                ephemeral=True
            )


class Discharge(commands.Cog):
    """
    Cog for /discharge command.
    
    Allows users to request discharge with approval workflow.
    """
    
    def __init__(self, bot: commands.Bot, database, roblox_api, command_logger):
        """
        Initialize Discharge cog.
        
        Args:
            bot: Discord bot instance
            database: BotDatabase instance
            roblox_api: RobloxAPICache instance
            command_logger: Command logging function
        """
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.rate_limiter = RateLimiter(max_uses=5, time_window=60)
    
    @app_commands.command(name="discharge", description="Request discharge from the server")
    @app_commands.describe(
        reason="Reason for requesting discharge"
    )
    async def discharge(
        self,
        interaction: discord.Interaction,
        reason: str
    ):
        """
        Handle /discharge command.
        
        Args:
            interaction: Discord interaction
            reason: Reason for discharge
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Check rate limit
            allowed, retry_after = self.rate_limiter.check_rate_limit(
                interaction.user.id,
                "discharge"
            )
            
            if not allowed:
                await interaction.followup.send(
                    f"❌ You're using commands too quickly! Please wait {retry_after} seconds.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "discharge",
                    {"reason": "rate_limited"},
                    success=False,
                    error="Rate limited"
                )
                return
            
            # Validate reason (no specific length limit, but keep it reasonable)
            try:
                validate_reason_length(reason, max_length=2000)
            except ValidationError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                await self.command_logger(
                    interaction,
                    "discharge",
                    {"reason": "invalid"},
                    success=False,
                    error=str(e)
                )
                return
            
            # Check join date (must be member for at least 7 days)
            # Skip this check in test mode
            test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
            
            if not interaction.user.joined_at:
                await interaction.followup.send(
                    "❌ Could not determine your join date. Please contact an administrator.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "discharge",
                    {"reason": reason[:50]},
                    success=False,
                    error="Join date unavailable"
                )
                return
            
            join_date = interaction.user.joined_at
            current_date = datetime.now(timezone.utc)
            # Ensure both are timezone-aware for comparison
            if join_date.tzinfo is None:
                join_date = join_date.replace(tzinfo=timezone.utc)
            days_since_join = (current_date - join_date).days
            
            # Only enforce 7-day requirement if not in test mode
            if not test_mode and days_since_join < 7:
                await interaction.followup.send(
                    f"❌ You must be a member for at least 7 days before requesting discharge.\n"
                    f"You joined {days_since_join} day(s) ago. Please wait {7 - days_since_join} more day(s).",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "discharge",
                    {"reason": reason[:50], "days_since_join": days_since_join},
                    success=False,
                    error=f"Joined only {days_since_join} days ago"
                )
                return
            
            # Fetch Roblox data
            roblox_user_id = int(os.getenv('ROBLOX_USER_ID', 296030103))
            roblox_group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))
            discharge_ping_role_id = int(os.getenv('DISCHARGE_PING_ROLE_ID', 0))
            
            footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
            group_icon_url = await self.roblox_api.get_group_icon(roblox_group_id)
            
            # Create embed
            embed = await create_discharge_request_embed(
                user=interaction.user,
                reason=reason,
                join_date=join_date,
                request_date=datetime.now(timezone.utc),
                group_icon_url=group_icon_url,
                footer_icon_url=footer_icon_url
            )
            
            # Get discharge request channel
            discharge_channel_id = int(os.getenv('DISCHARGE_REQUEST_CHANNEL_ID', 0))
            discharge_channel = self.bot.get_channel(discharge_channel_id)
            
            if not discharge_channel:
                await interaction.followup.send(
                    "❌ Discharge request channel not found. Please contact an administrator.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "discharge",
                    {"reason": reason[:50]},
                    success=False,
                    error="Channel not found"
                )
                return
            
            # Send with buttons
            discharge_data = {
                'user_id': interaction.user.id,
                'reason': reason,
                'message_id': 0  # Will be updated after sending
            }
            
            view = DischargeButtons(self.bot, self.database, self.roblox_api, self.command_logger, discharge_data)
            # Send ping outside embed as message content
            message = await discharge_channel.send(content=f"<@&{discharge_ping_role_id}>", embed=embed, view=view)
            
            # Update discharge data with message ID and store in database
            discharge_data['message_id'] = message.id
            await self.database.add_discharge_request(
                user_id=interaction.user.id,
                reason=reason,
                message_id=message.id
            )
            
            # Confirm to user
            await interaction.followup.send(
                f"✅ Your discharge request has been submitted and is pending approval.\n"
                f"**Member Since:** {join_date.strftime('%m/%d/%Y')} ({days_since_join} days)",
                ephemeral=True
            )
            
            # Log success
            await self.command_logger(
                interaction,
                "discharge",
                {"reason": reason[:50], "days_since_join": days_since_join},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error in discharge command: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request. Please try again later.",
                    ephemeral=True
                )
            except:
                pass
            
            await self.command_logger(
                interaction,
                "discharge",
                {"reason": reason[:50] if reason else "error"},
                success=False,
                error=f"Internal error: {type(e).__name__}"
            )


async def setup(bot: commands.Bot):
    """
    Setup function for loading cog.
    
    Args:
        bot: Discord bot instance
    """
    database = bot.database
    roblox_api = bot.roblox_api
    command_logger = bot.command_logger
    
    await bot.add_cog(Discharge(bot, database, roblox_api, command_logger))
    logger.info("Discharge cog loaded")
