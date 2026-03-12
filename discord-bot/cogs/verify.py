"""Roblox account verification — /verify username:<roblox username or ID>

The flow:
  1. User runs /verify
  2. Bot generates a unique token (4 random words) and stores it with a 15 min expiry
  3. User pastes the token into their Roblox profile About section and hits Save
  4. User clicks "Done" — bot fetches their live profile and checks for the token
  5. If found: Discord ID is linked to their EP record and the token is deleted
"""

import secrets
import logging
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# word pool for token generation — 4 random words gives ~500 million combinations
# which is way more than enough for a discord bot of any realistic size
_WORDS = [
    "amber", "anvil", "arrow", "atlas", "azure", "badger", "birch", "bison",
    "blaze", "bloom", "brave", "breach", "cedar", "cipher", "cliff", "cloud",
    "cobra", "comet", "coral", "crane", "crater", "creek", "crest", "crimson",
    "crystal", "dagger", "delta", "dingo", "dusk", "eagle", "echo", "ember",
    "falcon", "fern", "fjord", "flame", "flare", "flint", "flume", "forge",
    "frost", "gale", "gecko", "geyser", "ghost", "glacier", "glint", "grove",
    "gust", "haven", "haze", "heron", "hyena", "indigo", "inlet", "jade",
    "jaguar", "jasper", "javelin", "jungle", "kelp", "keystone", "lance",
    "larch", "lavender", "ledge", "llama", "lunar", "lynx", "maple", "marble",
    "marsh", "marten", "maroon", "meadow", "mist", "moose", "mystic", "nomad",
    "obsidian", "ocean", "olive", "onyx", "opal", "osprey", "otter", "panda",
    "peak", "phantom", "pine", "prism", "quartz", "quasar", "raven", "reef",
    "rhino", "ridge", "river", "robin", "rocky", "rogue", "rune", "russet",
    "saber", "sage", "scarlet", "shard", "sierra", "signal", "silver", "slate",
    "solar", "spark", "stag", "steel", "stone", "storm", "summit", "swift",
    "teal", "thorn", "tiger", "titan", "tundra", "turret", "umbra", "valley",
    "valor", "vapor", "vault", "veldt", "viper", "violet", "vista", "walrus",
    "wave", "willow", "wisp", "wolf", "zenith", "zephyr", "zebra",
]


def _generate_token() -> str:
    """pick 4 random words — collision chance is essentially zero at bot scale"""
    return "-".join(secrets.choice(_WORDS) for _ in range(4))


async def _unique_token(database) -> str:
    """keep generating until we get one that isn't already pending"""
    for _ in range(10):
        token = _generate_token()
        # check it's not already in use (astronomically unlikely but worth checking)
        existing = [
            v for v in database.data.get("pending_verifications", [])
            if v["token"] == token
        ]
        if not existing:
            return token
    # if somehow we hit 10 collisions, fall back to a purely random hex token
    return f"verify-{secrets.token_hex(8)}"


class VerifyView(discord.ui.View):
    def __init__(self, bot, database, roblox_api, roblox_user_id, roblox_username, token, requester):
        super().__init__(timeout=900)  # 15 minutes, same as the token expiry
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api
        self.roblox_user_id = roblox_user_id
        self.roblox_username = roblox_username
        self.token = token
        self.requester = requester

    async def on_timeout(self):
        # token is already expired by now so just clean it up
        await self.database.remove_pending_verification(self.requester.id)

    @discord.ui.button(label="✅ Done — I added it", style=discord.ButtonStyle.green)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        # only the person who ran /verify can press this
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ This isn't your verification.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # make sure the token hasn't expired yet
        pending = await self.database.get_pending_verification(self.requester.id)
        if not pending:
            await interaction.followup.send(
                "❌ Your verification token has expired. Run `/verify` again to get a new one.",
                ephemeral=True
            )
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
            self.stop()
            return

        # fetch the live profile — skip cache so we always get the latest blurb
        description = await self.roblox_api.get_user_description(self.roblox_user_id)
        if description is None:
            await interaction.followup.send(
                "❌ Couldn't reach Roblox's API right now. Wait a moment and try again.",
                ephemeral=True
            )
            return

        if self.token.lower() not in description.lower():
            await interaction.followup.send(
                f"❌ Couldn't find your token in **{self.roblox_username}**'s About section.\n\n"
                f"Make sure you:\n"
                f"• Pasted the token exactly as shown\n"
                f"• Clicked **Save** on your Roblox profile\n"
                f"• Are editing the right account\n\n"
                f"Then click **Done** again.",
                ephemeral=True
            )
            return

        # token found — link the accounts and delete the pending token
        await self.database.remove_pending_verification(self.requester.id)
        record = await self.database.link_discord_to_roblox(
            self.requester.id, self.roblox_user_id, self.roblox_username
        )

        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        self.stop()

        await interaction.followup.send(
            f"✅ **Verified!** Your Discord account is now linked to **{self.roblox_username}**.\n"
            f"You can remove the token from your profile now.",
            ephemeral=True
        )

        logger.info(
            f"verified: discord {self.requester.id} ({self.requester}) "
            f"→ roblox {self.roblox_username} ({self.roblox_user_id})"
        )

        # post to the log channel so staff can see it
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Roblox Account Verified",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Discord",       value=self.requester.mention,     inline=True)
            embed.add_field(name="Roblox",         value=self.roblox_username,       inline=True)
            embed.add_field(name="Roblox ID",      value=str(self.roblox_user_id),   inline=True)
            embed.add_field(name="EP",             value=str(record.get("ep", 0)),   inline=True)
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"failed to post verify log: {e}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ This isn't your verification.", ephemeral=True
            )
            return

        await self.database.remove_pending_verification(self.requester.id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ Verification cancelled.", ephemeral=True)
        self.stop()


class Verify(commands.Cog):

    def __init__(self, bot: commands.Bot, database, roblox_api):
        self.bot = bot
        self.database = database
        self.roblox_api = roblox_api

    @app_commands.command(name="verify", description="Link your Roblox account to your Discord")
    @app_commands.describe(username="Your Roblox username or numeric user ID")
    async def verify(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True)

        username = username.strip()

        # figure out if they passed a UID or a username
        if username.isdigit():
            roblox_user_id = int(username)
            roblox_username = await self.roblox_api.get_username_by_id(roblox_user_id)
            if not roblox_username:
                await interaction.followup.send(
                    f"❌ No Roblox account found for user ID **{roblox_user_id}**.",
                    ephemeral=True
                )
                return
        else:
            roblox_user_id = await self.roblox_api.get_user_id_by_username(username)
            roblox_username = username
            if not roblox_user_id:
                await interaction.followup.send(
                    f"❌ No Roblox account found for username **{username}**. "
                    f"Double-check the spelling.",
                    ephemeral=True
                )
                return

        # check if this Roblox account is already linked to someone else
        ep_record = await self.database.get_ep_record(roblox_user_id)
        if ep_record and ep_record.get("discord_user_id"):
            if ep_record["discord_user_id"] == interaction.user.id:
                await interaction.followup.send(
                    f"✅ You're already verified as **{roblox_username}**.",
                    ephemeral=True
                )
                return
            else:
                await interaction.followup.send(
                    f"❌ **{roblox_username}** is already linked to a different Discord account.\n"
                    f"If this is your account, contact a staff member.",
                    ephemeral=True
                )
                return

        # generate a unique token and store it
        token = await _unique_token(self.database)
        await self.database.add_pending_verification(
            discord_user_id=interaction.user.id,
            roblox_user_id=roblox_user_id,
            roblox_username=roblox_username,
            token=token,
        )

        embed = discord.Embed(
            title="Roblox Account Verification",
            description=(
                f"To verify **{roblox_username}** is your account, add this token to "
                f"your Roblox profile's **About** section, then click **Done**."
            ),
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Your Token",
            value=f"```\n{token}\n```",
            inline=False
        )
        embed.add_field(
            name="Steps",
            value=(
                "1. Go to [roblox.com](https://www.roblox.com) and open your profile\n"
                "2. Click **Edit Profile** → **About** section\n"
                "3. Paste the token anywhere in the text box\n"
                "4. Click **Save**, then come back here and hit **Done**"
            ),
            inline=False
        )
        embed.set_footer(text="Token expires in 15 minutes. You can remove it from your profile after verifying.")

        view = VerifyView(
            self.bot, self.database, self.roblox_api,
            roblox_user_id, roblox_username, token, interaction.user
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot, bot.database, bot.roblox_api))
    logger.info("Verify cog loaded")
