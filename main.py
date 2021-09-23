
import os
import discord
from discord.ext import commands
from src.CLI import CLI


cogs = [CLI]
client = commands.Bot(command_prefix='-', intents = discord.Intents.all())

for i in range(len(cogs)):
  cogs[i].setup(client)

client.run(os.environ['BOT_TOKEN'])