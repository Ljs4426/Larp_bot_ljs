import discord
from datetime import datetime
from typing import Optional
import os


def get_embed_color() -> int:
    try:
        return int(os.getenv('EMBED_COLOR', '0xFFFF00'), 16)
    except ValueError:
        return 0xFFFF00


def get_footer_text() -> str:
    return os.getenv('FOOTER_TEXT', '327th star corps development bot | developed by: ljs4426')


async def create_request_aid_embed(
    user: discord.Member,
    funds_needed: int,
    reason: str,
    proof_url: str,
    group_icon_url: str,
    footer_icon_url: str
) -> discord.Embed:
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
    embed = discord.Embed(
        title="Inactivity Notice Denied",
        description="Your inactivity notice has been denied.",
        color=0xFF0000
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
    embed = discord.Embed(
        title="Discharge Accepted",
        color=get_embed_color()
    )

    embed.set_thumbnail(url=group_icon_url)

    # handle new username system (no discriminator)
    username_display = f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name
    user_field_value = f"{user.mention} ({username_display})"

    embed.add_field(name="User", value=user_field_value, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text=get_footer_text(), icon_url=footer_icon_url)

    return embed
