import os
import logging
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Ensure data dirs exist
        Path("data").mkdir(parents=True, exist_ok=True)
        Path("data/backups").mkdir(parents=True, exist_ok=True)

        # Load cogs BEFORE syncing commands
        await self.load_extension("cogs.study")

        guild = discord.Object(int(GUILD_ID)) if (GUILD_ID and GUILD_ID.isdigit()) else None
        if guild:
            await self.tree.sync(guild=guild)
            logging.info(f"Synced commands to guild {GUILD_ID}")
        else:
            await self.tree.sync()
            logging.info("Globally synced commands (can take a while)")

bot = Bot()

@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

bot.run(TOKEN)
