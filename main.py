import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from src.CLI import CLI

load_dotenv()

cogs = [CLI]
client = commands.Bot(command_prefix='-', intents = discord.Intents.all())

for i in range(len(cogs)):
  cogs[i].setup(client)

client.run(os.getenv('BOT_TOKEN'))