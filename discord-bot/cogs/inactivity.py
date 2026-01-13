import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from datetime import datetime, timedelta, timezone

from utils.validators import (
    validate_date_string,
    validate_reason_length,
    ValidationError
)
from utils.rate_limit import RateLimiter
from utils.embeds import (
    create_inactivity_notice_embed,
    create_inactivity_denial_embed
)

logger = logging.getLogger(__name__)


class EmergencySelectButtons(discord.ui.View):
    def __init__(self, interaction_data):
        super().__init__(timeout=60)
        self.interaction_data = interaction_data
        self.is_emergency = None
    
    @discord.ui.button(label="Yes - Emergency", style=discord.ButtonStyle.red, custom_id="emergency_yes")
    async def emergency_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_emergency = True
        self.stop()
        await interaction.response.edit_message(
            content="✅ Marked as **EMERGENCY** inactivity notice. Submitting...",
            view=None
        )
    
    @discord.ui.button(label="No - Regular", style=discord.ButtonStyle.gray, custom_id="emergency_no")
    async def emergency_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.is_emergency = False
        self.stop()
        await interaction.response.edit_message(
            content="✅ Marked as regular inactivity notice. Submitting...",
            view=None
        )


class EndEarlyDMButtons(discord.ui.View):
    def __init__(self, bot, database, user_id, message_id, end_date):
        super().__init__(timeout=None)
        self.bot = bot
        self.database = database
        self.user_id = user_id
        self.message_id = message_id
        self.end_date = end_date
    
    @discord.ui.button(label="End Inactivity Early", style=discord.ButtonStyle.red, custom_id="dm_end_early")
    async def end_early_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            guild = None
            member = None
            for g in self.bot.guilds:
                member = g.get_member(self.user_id)
                if member:
                    guild = g
                    break
            
            if not guild or not member:
                await interaction.followup.send(
                    "❌ Could not find you in the server.",
                    ephemeral=True
                )
                return
            
            inactivity_role_id = int(os.getenv('INACTIVITY_ROLE_ID', 0))
            inactivity_role = guild.get_role(inactivity_role_id)
            
            if inactivity_role and inactivity_role in member.roles:
                await member.remove_roles(inactivity_role, reason="Inactivity ended early by user via DM")
                logger.info(f"Removed inactivity role from {member} (ended early via DM)")
            
            cooldown_role_id = int(os.getenv('INACTIVITY_COOLDOWN_ROLE_ID', 0))
            cooldown_role = guild.get_role(cooldown_role_id)
            
            if cooldown_role:
                await member.add_roles(cooldown_role, reason="Inactivity ended early - cooldown started")
                logger.info(f"Added cooldown role to {member} (ended early via DM)")

                cooldown_end = datetime.now(timezone.utc) + timedelta(days=14)
                await self.database.add_cooldown(self.user_id, cooldown_end)
            
            await self.database.update_inactivity_status(
                self.message_id,
                'ended_early',
                self.user_id
            )
            
            inactivity_channel_id = int(os.getenv('INACTIVITY_CHANNEL_ID', 0))
            inactivity_channel = guild.get_channel(inactivity_channel_id)
            if inactivity_channel:
                try:
                    message = await inactivity_channel.fetch_message(self.message_id)
                    await message.delete()
                    logger.info(f"Deleted inactivity notice message {self.message_id} (ended early via DM)")
                except discord.NotFound:
                    logger.warning(f"Message {self.message_id} not found")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to delete message {self.message_id}")
            
            for item in self.children:
                item.disabled = True

            await interaction.message.edit(view=self)

            await interaction.followup.send(
                "✅ Your inactivity notice has been ended early.\n"
                "The inactivity role has been removed and you now have a 14-day cooldown "
                "before you can request another inactivity notice.",
                ephemeral=True
            )
            
            logger.info(f"Inactivity ended early via DM for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error ending inactivity early via DM: {e}")
            await interaction.followup.send(
                "❌ An error occurred while ending your inactivity notice.",
                ephemeral=True
            )


class InactivityButtons(discord.ui.View):
    def __init__(self, bot, database, roblox_api, command_logger, notice_data):
        super().__init__(timeout=None)
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.notice_data = notice_data
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        
        await interaction.response.send_message(
            "❌ You don't have permission to approve/deny inactivity notices. (Requires Manage Server permission)",
            ephemeral=True
        )
        return False
    
    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="inactivity_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = self.notice_data['user_id']
            message_id = self.notice_data['message_id']
            
            guild = interaction.guild
            member = guild.get_member(user_id)

            if not member:
                await interaction.followup.send(
                    "❌ User not found in server.",
                    ephemeral=True
                )
                return

            inactivity_role_id = int(os.getenv('INACTIVITY_ROLE_ID', 0))
            inactivity_role = guild.get_role(inactivity_role_id)
            
            if not inactivity_role:
                await interaction.followup.send(
                    "❌ Inactivity role not found. Please contact an administrator.",
                    ephemeral=True
                )
                return
            
            await member.add_roles(inactivity_role, reason=f"Inactivity approved by {interaction.user}")

            await self.database.update_inactivity_status(
                message_id,
                'approved',
                interaction.user.id
            )
            
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            embed.add_field(
                name="Status",
                value=f"✅ APPROVED by {interaction.user.mention}",
                inline=False
            )

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            try:
                end_early_view = EndEarlyDMButtons(
                    bot=self.bot,
                    database=self.database,
                    user_id=user_id,
                    message_id=message_id,
                    end_date=self.notice_data['end_date']
                )
                
                await member.send(
                    f"✅ Your inactivity notice has been approved! "
                    f"You have been given the inactivity role until {self.notice_data['end_date'].strftime('%m/%d/%Y')}.\n\n"
                    f"You can end your inactivity early at any time using the button below.",
                    view=end_early_view
                )
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user_id} about approved inactivity")
            
            await interaction.followup.send(
                f"✅ Inactivity notice approved for {member.mention}",
                ephemeral=True
            )
            
            logger.info(f"Inactivity notice approved for user {user_id} by {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Error approving inactivity notice: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while approving the notice.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="inactivity_deny")
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            user_id = self.notice_data['user_id']
            message_id = self.notice_data['message_id']
            
            guild = interaction.guild
            member = guild.get_member(user_id)

            if not member:
                await interaction.followup.send(
                    "❌ User not found in server.",
                    ephemeral=True
                )
                return

            await self.database.update_inactivity_status(
                message_id,
                'denied',
                interaction.user.id
            )

            embed = interaction.message.embeds[0]
            embed.color = discord.Color.red()
            embed.add_field(
                name="Status",
                value=f"❌ DENIED by {interaction.user.mention}",
                inline=False
            )

            for item in self.children:
                item.disabled = True

            await interaction.message.edit(embed=embed, view=self)

            try:
                roblox_user_id = int(os.getenv('ROBLOX_USER_ID', 296030103))
                footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
                
                denial_embed = await create_inactivity_denial_embed(
                    start_date=self.notice_data['start_date'],
                    end_date=self.notice_data['end_date'],
                    reason=self.notice_data['reason'],
                    denier_id=interaction.user.id,
                    footer_icon_url=footer_icon_url
                )
                
                await member.send(embed=denial_embed)
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user_id} about denied inactivity")
            except Exception as e:
                logger.error(f"Error sending denial DM: {e}")
            
            await interaction.followup.send(
                f"✅ Inactivity notice denied for {member.mention}",
                ephemeral=True
            )
            
            logger.info(f"Inactivity notice denied for user {user_id} by {interaction.user.id}")
            
        except Exception as e:
            logger.error(f"Error denying inactivity notice: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ An error occurred while denying the notice.",
                ephemeral=True
            )


class Inactivity(commands.Cog):
    def __init__(self, bot, database, roblox_api, command_logger):
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.rate_limiter = RateLimiter(max_uses=5, time_window=60)
    
    @app_commands.command(name="inactivity-notice", description="Submit an inactivity notice")
    @app_commands.describe(
        enddate="End date (MM/DD/YYYY or YYYY-MM-DD)",
        reason="Reason for inactivity (max 1024 characters)"
    )
    async def inactivity_notice(
        self,
        interaction: discord.Interaction,
        enddate: str,
        reason: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            allowed, retry_after = self.rate_limiter.check_rate_limit(
                interaction.user.id,
                "inactivity-notice"
            )
            
            if not allowed:
                await interaction.followup.send(
                    f"❌ You're using commands too quickly! Please wait {retry_after} seconds.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": "rate_limited"},
                    success=False,
                    error="Rate limited"
                )
                return
            
            try:
                validate_reason_length(reason, max_length=1024)
            except ValidationError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": "invalid"},
                    success=False,
                    error=str(e)
                )
                return
            
            try:
                parsed_end_date, _ = validate_date_string(enddate)
                if parsed_end_date.tzinfo is None:
                    parsed_end_date = parsed_end_date.replace(tzinfo=timezone.utc)
            except ValidationError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": reason[:50]},
                    success=False,
                    error=str(e)
                )
                return
            
            current_date = datetime.now(timezone.utc)
            days_difference = (parsed_end_date - current_date).days
            
            max_days = int(os.getenv('MAX_INACTIVITY_DAYS', 30))
            if days_difference > max_days:
                await interaction.followup.send(
                    f"❌ End date cannot be more than {max_days} days from today. "
                    f"Your requested end date is {days_difference} days away.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": reason[:50]},
                    success=False,
                    error=f"Date too far ({days_difference} days)"
                )
                return
            
            if days_difference < 0:
                await interaction.followup.send(
                    "❌ End date cannot be in the past.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": reason[:50]},
                    success=False,
                    error="Date in past"
                )
                return
            
            inactivity_role_id = int(os.getenv('INACTIVITY_ROLE_ID', 0))
            inactivity_role = interaction.guild.get_role(inactivity_role_id)
            
            has_inactivity_role = inactivity_role and inactivity_role in interaction.user.roles

            cooldown_role_id = int(os.getenv('INACTIVITY_COOLDOWN_ROLE_ID', 0))
            cooldown_role = interaction.guild.get_role(cooldown_role_id)
            
            has_cooldown_role = cooldown_role and cooldown_role in interaction.user.roles

            roblox_user_id = int(os.getenv('ROBLOX_USER_ID', 296030103))
            roblox_group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))
            
            footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
            group_icon_url = await self.roblox_api.get_group_icon(roblox_group_id)
            
            is_emergency = False

            if has_cooldown_role:
                emergency_view = EmergencySelectButtons({
                    'enddate': enddate,
                    'reason': reason,
                    'parsed_end_date': parsed_end_date,
                    'current_date': current_date
                })
                
                await interaction.followup.send(
                    "⚠️ **You are currently on cooldown from a previous inactivity notice.**\n\n"
                    "🚨 Is this an EMERGENCY that requires immediate attention?\n"
                    "Emergency requests will override your cooldown.\n\n"
                    "**Select No if this is not an emergency.**",
                    view=emergency_view,
                    ephemeral=True
                )
                
                await emergency_view.wait()

                if emergency_view.is_emergency is None:
                    await interaction.followup.send(
                        "❌ Selection timed out. Please try the command again.",
                        ephemeral=True
                    )
                    return

                if not emergency_view.is_emergency:
                    await interaction.followup.send(
                        "❌ You are on cooldown from a previous inactivity notice. "
                        "If this is an emergency, please use the emergency option.",
                        ephemeral=True
                    )
                    await self.command_logger(
                        interaction,
                        "inactivity-notice",
                        {"enddate": enddate, "reason": reason[:50]},
                        success=False,
                        error="User on cooldown"
                    )
                    return
                
                is_emergency = True

            if has_inactivity_role:
                emergency_view = EmergencySelectButtons({
                    'enddate': enddate,
                    'reason': reason,
                    'parsed_end_date': parsed_end_date,
                    'current_date': current_date
                })
                
                await interaction.followup.send(
                    "⚠️ **You already have an active inactivity notice.**\n\n"
                    "🚨 Is this an EMERGENCY that requires immediate attention?\n"
                    "Emergency notices will override your current inactivity notice.\n\n"
                    "**Select No if this is not an emergency.**",
                    view=emergency_view,
                    ephemeral=True
                )
                
                await emergency_view.wait()

                if emergency_view.is_emergency is None:
                    await interaction.followup.send(
                        "❌ Selection timed out. Please try the command again.",
                        ephemeral=True
                    )
                    return

                if not emergency_view.is_emergency:
                    await interaction.followup.send(
                        "❌ You already have an active inactivity notice. "
                        "If this is an emergency, please use the emergency option.",
                        ephemeral=True
                    )
                    await self.command_logger(
                        interaction,
                        "inactivity-notice",
                        {"enddate": enddate, "reason": reason[:50]},
                        success=False,
                        error="Already has inactivity role"
                    )
                    return
                
                is_emergency = True

            embed = await create_inactivity_notice_embed(
                user=interaction.user,
                start_date=current_date,
                end_date=parsed_end_date,
                reason=reason,
                group_icon_url=group_icon_url,
                footer_icon_url=footer_icon_url,
                is_emergency=is_emergency
            )
            
            inactivity_channel_id = int(os.getenv('INACTIVITY_CHANNEL_ID', 0))
            inactivity_channel = self.bot.get_channel(inactivity_channel_id)
            
            if not inactivity_channel:
                await interaction.followup.send(
                    "❌ Inactivity channel not found. Please contact an administrator.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "inactivity-notice",
                    {"enddate": enddate, "reason": reason[:50]},
                    success=False,
                    error="Channel not found"
                )
                return
            
            notice_data = {
                'user_id': interaction.user.id,
                'start_date': current_date,
                'end_date': parsed_end_date,
                'reason': reason,
                'message_id': 0,
                'is_emergency': is_emergency
            }
            
            view = InactivityButtons(self.bot, self.database, self.roblox_api, self.command_logger, notice_data)
            message = await inactivity_channel.send(embed=embed, view=view)
            
            notice_data['message_id'] = message.id
            await self.database.add_inactivity_notice(
                user_id=interaction.user.id,
                start_date=current_date,
                end_date=parsed_end_date,
                reason=reason,
                message_id=message.id,
                is_emergency=is_emergency
            )
            
            emergency_text = " (marked as EMERGENCY)" if is_emergency else ""
            await interaction.followup.send(
                f"✅ Your inactivity notice has been submitted and is pending approval{emergency_text}.\n"
                f"**End Date:** {parsed_end_date.strftime('%m/%d/%Y')}\n"
                f"**Duration:** {days_difference} days",
                ephemeral=True
            )
            
            await self.command_logger(
                interaction,
                "inactivity-notice",
                {"enddate": enddate, "reason": reason[:50], "days": days_difference},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error in inactivity-notice command: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request. Please try again later.",
                    ephemeral=True
                )
            except:
                pass
            
            await self.command_logger(
                interaction,
                "inactivity-notice",
                {"enddate": enddate, "reason": reason[:50] if reason else "error"},
                success=False,
                error=f"Internal error: {type(e).__name__}"
            )


async def setup(bot: commands.Bot):
    database = bot.database
    roblox_api = bot.roblox_api
    command_logger = bot.command_logger
    
    await bot.add_cog(Inactivity(bot, database, roblox_api, command_logger))
    logger.info("Inactivity cog loaded")
