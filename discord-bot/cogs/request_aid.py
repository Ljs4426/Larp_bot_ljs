import discord
from discord import app_commands
from discord.ext import commands
import os
import logging
from datetime import datetime

from utils.validators import (
    validate_funds_needed,
    validate_url,
    validate_image_attachment,
    validate_reason_length,
    ValidationError
)
from utils.rate_limit import RateLimiter
from utils.embeds import create_request_aid_embed

logger = logging.getLogger(__name__)


class RequestAid(commands.Cog):
    def __init__(self, bot, roblox_api, command_logger):
        self.bot = bot
        self.roblox_api = roblox_api
        self.command_logger = command_logger
        self.rate_limiter = RateLimiter(max_uses=5, time_window=60)
    
    @app_commands.command(name="request-aid", description="Request military aid funds")
    @app_commands.describe(
        fundsneeded="Amount of funds needed (1-999,999,999)",
        reason="Reason for requesting funds (max 1024 characters)",
        proof="Proof URL (HTTPS only)",
        attachment="Or attach an image file (PNG, JPG, GIF, WebP, max 10MB)"
    )
    async def request_aid(
        self,
        interaction: discord.Interaction,
        fundsneeded: int,
        reason: str,
        proof: str = None,
        attachment: discord.Attachment = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            allowed, retry_after = self.rate_limiter.check_rate_limit(
                interaction.user.id,
                "request-aid"
            )
            
            if not allowed:
                await interaction.followup.send(
                    f"❌ You're using commands too quickly! Please wait {retry_after} seconds.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded, "proof": "rate_limited"},
                    success=False,
                    error="Rate limited"
                )
                return
            
            try:
                validate_funds_needed(fundsneeded)
            except ValidationError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded},
                    success=False,
                    error=str(e)
                )
                return
            
            try:
                validate_reason_length(reason, max_length=1024)
            except ValidationError as e:
                await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded, "reason": "invalid"},
                    success=False,
                    error=str(e)
                )
                return
            
            proof_url = None

            if attachment:
                try:
                    validate_image_attachment(attachment)
                    proof_url = attachment.url
                except ValidationError as e:
                    await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                    await self.command_logger(
                        interaction,
                        "request-aid",
                        {"fundsneeded": fundsneeded, "proof": "invalid_attachment"},
                        success=False,
                        error=str(e)
                    )
                    return
            elif proof:
                try:
                    validate_url(proof)
                    proof_url = proof
                except ValidationError as e:
                    await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)
                    await self.command_logger(
                        interaction,
                        "request-aid",
                        {"fundsneeded": fundsneeded, "proof": proof},
                        success=False,
                        error=str(e)
                    )
                    return
            else:
                await interaction.followup.send(
                    "❌ You must provide proof either as a URL or an image attachment.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded, "proof": "none"},
                    success=False,
                    error="No proof provided"
                )
                return
            
            roblox_user_id = int(os.getenv('ROBLOX_USER_ID', 296030103))
            roblox_group_id = int(os.getenv('ROBLOX_GROUP_ID', 5674426))
            
            footer_icon_url = await self.roblox_api.get_user_avatar(roblox_user_id)
            group_icon_url = await self.roblox_api.get_group_icon(roblox_group_id)
            
            embed = await create_request_aid_embed(
                user=interaction.user,
                funds_needed=fundsneeded,
                reason=reason,
                proof_url=proof_url,
                group_icon_url=group_icon_url,
                footer_icon_url=footer_icon_url
            )
            
            aid_channel_id = int(os.getenv('AID_REQUEST_CHANNEL_ID', 0))
            aid_channel = self.bot.get_channel(aid_channel_id)
            
            if not aid_channel:
                await interaction.followup.send(
                    "❌ Aid request channel not found. Please contact an administrator.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded, "proof": proof_url},
                    success=False,
                    error="Channel not found"
                )
                return
            
            permissions = aid_channel.permissions_for(aid_channel.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await interaction.followup.send(
                    "❌ I don't have permission to send messages in the aid request channel.",
                    ephemeral=True
                )
                await self.command_logger(
                    interaction,
                    "request-aid",
                    {"fundsneeded": fundsneeded, "proof": proof_url},
                    success=False,
                    error="Missing permissions"
                )
                return
            
            await aid_channel.send(embed=embed)

            await interaction.followup.send(
                f"✅ Your aid request for **{fundsneeded:,}** has been submitted!",
                ephemeral=True
            )
            
            await self.command_logger(
                interaction,
                "request-aid",
                {"fundsneeded": fundsneeded, "proof": proof_url},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error in request-aid command: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ An error occurred while processing your request. Please try again later.",
                    ephemeral=True
                )
            except:
                pass
            
            await self.command_logger(
                interaction,
                "request-aid",
                {"fundsneeded": fundsneeded, "proof": proof or "attachment"},
                success=False,
                error=f"Internal error: {type(e).__name__}"
            )


async def setup(bot: commands.Bot):
    roblox_api = bot.roblox_api
    command_logger = bot.command_logger
    
    await bot.add_cog(RequestAid(bot, roblox_api, command_logger))
    logger.info("RequestAid cog loaded")
