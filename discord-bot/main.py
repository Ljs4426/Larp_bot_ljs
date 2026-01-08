"""Discord bot entry point."""

import discord
from discord.ext import commands
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from dotenv import load_dotenv
import asyncio

from utils.roblox_api import RobloxAPICache
from storage.database import BotDatabase
from storage.scheduler import TaskScheduler
from api.server import start_api

load_dotenv()


def setup_logging():
    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        'bot_commands.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.WARNING)

    return logger

logger = setup_logging()


class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )

        self.roblox_api = RobloxAPICache()
        self.database   = BotDatabase('bot_data.json')
        self.scheduler  = None
        self.log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))

        logger.info("bot instance created")

    async def setup_hook(self):
        logger.info("running setup hook...")

        await self.database.load()
        logger.info("database loaded")

        cogs_config = {
            'cogs.request_aid': os.getenv('ENABLE_REQUEST_AID', 'true').lower() == 'true',
            'cogs.inactivity':  os.getenv('ENABLE_INACTIVITY',  'true').lower() == 'true',
            'cogs.discharge':   os.getenv('ENABLE_DISCHARGE',   'true').lower() == 'true',
            'cogs.ep':          os.getenv('ENABLE_EP',          'true').lower() == 'true',
            'cogs.log':         os.getenv('ENABLE_LOG',         'true').lower() == 'true',
            'cogs.report':      os.getenv('ENABLE_REPORT',      'true').lower() == 'true',
            'cogs.profile':     True,
            'cogs.backup':      os.getenv('ENABLE_BACKUP',      'true').lower() == 'true',
        }

        for cog, enabled in cogs_config.items():
            if not enabled:
                logger.info(f"skipping cog (disabled): {cog}")
                continue
            try:
                await self.load_extension(cog)
                logger.info(f"loaded cog: {cog}")
            except Exception as e:
                logger.error(f"failed to load cog {cog}: {e}", exc_info=True)

        self.scheduler = TaskScheduler(self, self.database)
        self.scheduler.start()
        logger.info("scheduler started")

        import signal as _signal
        try:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(
                _signal.SIGTERM,
                lambda: asyncio.create_task(self.close())
            )
            logger.info("SIGTERM handler registered")
        except (NotImplementedError, RuntimeError):
            logger.warning("SIGTERM handler not supported on this platform")

        # global sync — can take up to 1hr; guild sync in on_ready is instant
        try:
            synced = await self.tree.sync()
            logger.info(f"global sync: {len(synced)} commands")
        except Exception as e:
            logger.error(f"global sync failed: {e}", exc_info=True)

        if os.getenv('ENABLE_API', 'true').lower() == 'true':
            asyncio.create_task(start_api(self.database))

    async def on_ready(self):
        logger.info(f"logged in as {self.user} ({self.user.id})")
        logger.info(f"connected to {len(self.guilds)} guild(s)")

        for guild in self.guilds:
            try:
                synced = await self.tree.sync(guild=guild)
                logger.info(f"guild sync: {len(synced)} commands → {guild.name} ({guild.id})")
            except Exception as e:
                logger.error(f"guild sync failed for {guild.name}: {e}")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="327th Star Corps"
            )
        )

        await self.log_to_discord(
            f"🟢 **Bot Online**\n"
            f"Logged in as {self.user.mention}\n"
            f"Connected to {len(self.guilds)} server(s)"
        )

        if self.scheduler:
            asyncio.create_task(self.scheduler.sync_ep_records())

    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"joined guild: {guild.name} ({guild.id})")
        await self.log_to_discord(
            f"📥 **Joined Server**\n"
            f"Server: {guild.name}\n"
            f"Members: {guild.member_count}"
        )

    async def on_guild_remove(self, guild: discord.Guild):
        logger.info(f"left guild: {guild.name} ({guild.id})")
        await self.log_to_discord(f"📤 **Left Server**\nServer: {guild.name}")

    async def on_error(self, event: str, *args, **kwargs):
        logger.error(f"error in event {event}", exc_info=True)

    async def log_to_discord(self, message: str):
        try:
            if self.log_channel_id:
                channel = self.get_channel(self.log_channel_id)
                if channel:
                    await channel.send(message)
        except Exception as e:
            logger.error(f"discord log failed: {e}")

    async def command_logger(
        self,
        interaction: discord.Interaction,
        command_name: str,
        parameters: dict,
        success: bool,
        error: str = None
    ):
        params_str = ', '.join(f"{k}={v}" for k, v in parameters.items())
        status     = "SUCCESS" if success else "FAILED"
        user       = interaction.user
        username   = f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name

        log_msg = (
            f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}] "
            f"<@{user.id}> ({username}) used /{command_name} "
            f"params: {params_str} | {status}"
        )
        if error:
            log_msg += f" | {error}"

        logger.info(log_msg)

        try:
            if self.log_channel_id:
                channel = self.get_channel(self.log_channel_id)
                if channel:
                    embed = discord.Embed(
                        title=f"Command: /{command_name}",
                        color=discord.Color.green() if success else discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name="User",       value=f"{user.mention} ({username})", inline=False)
                    embed.add_field(name="Parameters", value=params_str or "None",           inline=False)
                    embed.add_field(name="Status",     value=status,                         inline=True)
                    if error:
                        embed.add_field(name="Error", value=error, inline=False)
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"command log failed: {e}")

    async def close(self):
        logger.info("shutting down...")

        backup_cog = self.cogs.get('Backup')
        if backup_cog:
            try:
                await backup_cog.go_offline()
            except Exception as e:
                logger.error(f"go_offline error: {e}")

        if self.scheduler:
            self.scheduler.stop()

        await self.roblox_api.close()
        await self.database.save()

        await self.log_to_discord("🔴 **Bot Offline** - Shutting down")
        await super().close()
        logger.info("shutdown complete")


async def main():
    required_vars = [
        'DISCORD_TOKEN',
        'ROBLOX_USER_ID',
        'ROBLOX_GROUP_ID',
        'LOG_CHANNEL_ID',
        'AID_REQUEST_CHANNEL_ID',
        'INACTIVITY_CHANNEL_ID',
        'DISCHARGE_REQUEST_CHANNEL_ID',
        'DISCHARGE_LOG_CHANNEL_ID',
        'INACTIVITY_ROLE_ID',
        'INACTIVITY_COOLDOWN_ROLE_ID',
        'DISCHARGE_PING_ROLE_ID',
        'DISCHARGE_LOG_PING_ROLE_ID'
    ]

    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not set")
        sys.exit(1)

    bot = DiscordBot()

    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        logger.info("keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"fatal error: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("stopped by user")
    except Exception as e:
        logger.error(f"fatal error: {e}", exc_info=True)
        sys.exit(1)
