"""Embed builder utilities for Discord bot."""

import discord
from datetime import datetime
from typing import Optional
import os


def get_embed_color() -> int:
    """
    Get embed color from environment variable.
    
    Returns:
        Hex color value (default yellow)
    """
    try:
        return int(os.getenv('EMBED_COLOR', '0xFFFF00'), 16)
    except ValueError:
        return 0xFFFF00  # Default yellow


def get_footer_text() -> str:
    server_name = os.getenv('REPORT_UNIT_NAME', '327th Star Corps')
    return f"{server_name} Assistant | Made by <@1027732252685250560>"


async def create_request_aid_embed(
    user: discord.Member,
    funds_needed: int,
    reason: str,
    proof_url: str,
    group_icon_url: str,
    footer_icon_url: str
) -> discord.Embed:
    """
    Create embed for military aid request.
    
    Args:
        user: Discord member making the request
        funds_needed: Amount of funds needed
        reason: Reason for requesting funds
        proof_url: URL to proof image
        group_icon_url: Roblox group icon URL
        footer_icon_url: Roblox user avatar URL
        
    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Military Aid",
        color=get_embed_color()
    )
    
    embed.set_thumbnail(url=group_icon_url)
    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(name="Requesting", value=f"{funds_needed:,}", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Proof", value=proof_url, inline=False)
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed


async def create_inactivity_notice_embed(
    user: discord.Member,
    start_date: datetime,
    end_date: datetime,
    reason: str,
    group_icon_url: str,
    footer_icon_url: str,
    is_emergency: bool = False
) -> discord.Embed:
    """
    Create embed for inactivity notice.
    
    Args:
        user: Discord member submitting notice
        start_date: Start date of inactivity
        end_date: End date of inactivity
        reason: Reason for inactivity
        group_icon_url: Roblox group icon URL
        footer_icon_url: Roblox user avatar URL
        is_emergency: Whether this is an emergency notice (changes color to red)
        
    Returns:
        Formatted Discord embed
    """
    # Use red color for emergency, default yellow for normal
    embed_color = 0xFF0000 if is_emergency else get_embed_color()
    
    title = "🚨 EMERGENCY Inactivity Notice" if is_emergency else "Inactivity Notice"
    
    embed = discord.Embed(
        title=title,
        color=embed_color
    )
    
    embed.set_thumbnail(url=group_icon_url)
    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(
        name="Start Date",
        value=start_date.strftime('%m/%d/%Y %H:%M:%S'),
        inline=True
    )
    embed.add_field(
        name="End Date",
        value=end_date.strftime('%m/%d/%Y'),
        inline=True
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    
    if is_emergency:
        embed.add_field(
            name="⚠️ Emergency Status",
            value="This is marked as an emergency inactivity notice.",
            inline=False
        )
    
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed


async def create_inactivity_denial_embed(
    start_date: datetime,
    end_date: datetime,
    reason: str,
    denier_id: int,
    footer_icon_url: str
) -> discord.Embed:
    """
    Create DM embed for denied inactivity notice.
    
    Args:
        start_date: Start date of inactivity
        end_date: End date of inactivity
        reason: Original reason submitted
        denier_id: ID of user who denied the request
        footer_icon_url: Roblox user avatar URL
        
    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Inactivity Notice Denied",
        description="Your inactivity notice has been denied.",
        color=0xFF0000  # Red
    )
    
    embed.add_field(
        name="Start Date",
        value=start_date.strftime('%m/%d/%Y %H:%M:%S'),
        inline=True
    )
    embed.add_field(
        name="End Date",
        value=end_date.strftime('%m/%d/%Y'),
        inline=True
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(
        name="Next Steps",
        value=f"Please contact <@{denier_id}> to understand why it was denied.",
        inline=False
    )
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed


async def create_discharge_request_embed(
    user: discord.Member,
    reason: str,
    join_date: datetime,
    request_date: datetime,
    group_icon_url: str,
    footer_icon_url: str
) -> discord.Embed:
    """
    Create embed for discharge request.
    
    Args:
        user: Discord member requesting discharge
        reason: Reason for discharge
        join_date: Date user joined the server
        request_date: Date of the request
        group_icon_url: Roblox group icon URL
        footer_icon_url: Roblox user avatar URL
        
    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Discharge Request",
        color=get_embed_color()
    )
    
    embed.set_thumbnail(url=group_icon_url)
    embed.add_field(name="User", value=user.mention, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(
        name="Join Date",
        value=join_date.strftime('%m/%d/%Y'),
        inline=True
    )
    embed.add_field(
        name="Request Date",
        value=request_date.strftime('%m/%d/%Y'),
        inline=True
    )
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed


async def create_discharge_goodbye_embed(
    group_icon_url: str,
    footer_icon_url: str
) -> discord.Embed:
    """
    Create goodbye DM embed for approved discharge.
    
    Args:
        group_icon_url: Roblox group icon URL
        footer_icon_url: Roblox user avatar URL
        
    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Discharge Accepted",
        color=get_embed_color()
    )
    
    embed.set_thumbnail(url=group_icon_url)
    embed.add_field(
        name="Goodbye",
        value="Thank you for your service to the 327th Star Corps. We hope to see you again!",
        inline=False
    )
    
    process_text = (
        "Please leave the Roblox group at [327th Star Corps](https://www.roblox.com/communities/5674426/327th-Star-Corps#!/about). "
        "Whether you are joining another division or not, please leave the group as soon as possible. "
        "If you join another divion while in the 327th roblox group you will not pass the tryout and can be blacklisted. "
    )
    embed.add_field(name="Process", value=process_text, inline=False)
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed


async def create_discharge_log_embed(
    user: discord.Member,
    reason: str,
    group_icon_url: str,
    footer_icon_url: str
) -> discord.Embed:
    """
    Create log embed for approved discharge.
    
    Args:
        user: Discord member who was discharged
        reason: Reason for discharge
        group_icon_url: Roblox group icon URL
        footer_icon_url: Roblox user avatar URL
        
    Returns:
        Formatted Discord embed
    """
    embed = discord.Embed(
        title="Discharge Accepted",
        color=get_embed_color()
    )
    
    embed.set_thumbnail(url=group_icon_url)
    
    # Format username with discriminator (handle new username system)
    username_display = f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name
    user_field_value = f"{user.mention} ({username_display})"
    
    embed.add_field(name="User", value=user_field_value, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)
    
    return embed
