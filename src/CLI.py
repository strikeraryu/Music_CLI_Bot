import discord
from discord.ext import commands, tasks
import youtube_dl
from .utils import getUrl
from .config import FFMPEG_OPTIONS, YDL_OPTIONS


class CLI(commands.Cog):
  def __init__(self, client):
    self.client = client
    self.server_queue = {}
    self.active_servers = {}

  @commands.command(description='Join voice channel')
  async def join(self, ctx):
    if ctx.author.voice is None:
      await ctx.send("You are not in any voice channel")
      return

    voice_channel = ctx.author.voice.channel

    if ctx.voice_client is None:
      await voice_channel.connect()
    else:
      await ctx.voice_client.move_to(voice_channel)

    self.active_servers[ctx.guild.id] = {
        'voice_client': ctx.voice_client,
        'channel': ctx.channel,
        'loop': False,
        'continue': True,
        }

    self.server_queue[ctx.guild.id] = []

    if not self.queue_check.is_running():
      self.queue_check.start()

  @commands.command(description='Disconnect from voice channel')
  async def disconnect(self, ctx):
    self.queue_check.stop()

    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return
    else:
      await ctx.voice_client.disconnect()
      await ctx.send('Bot left the voice channel')

    del self.active_servers[ctx.guild.id]
    del self.server_queue[ctx.guild.id]



  @commands.command(description='Play/resume song [song_name]')
  async def play(self, ctx, *, song=''):
    await self.join(ctx)

    if song.strip() == '':
      await self.resume(ctx)
      return

    self.active_servers[ctx.guild.id]['continue'] = True
    
    try:
      title, url = getUrl(song)
    except:
      await ctx.send(f'No song - {song[:30]}...')

    self.server_queue[ctx.guild.id] = self.server_queue.get(ctx.guild.id, [])
    self.server_queue[ctx.guild.id].append(title)
    await ctx.send(f'Added in queue - {title}')
      
  @commands.command(description='Pause song')
  async def pause(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    if ctx.voice_client.is_playing():
      ctx.voice_client.pause()
      await ctx.send('Paused ⏸')
    else:
      await ctx.send('No song playing')


  @commands.command(description='Resume song')
  async def resume(self, ctx):

    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    self.active_servers[ctx.guild.id]['continue'] = True
    if ctx.voice_client.is_paused():
      ctx.voice_client.resume()
      await ctx.send('Resume ▶')
    else:
      await ctx.send('No song in the queue')



  @commands.command(description='Stop song')
  async def stop(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return
      
    if ctx.voice_client.is_playing():
      ctx.voice_client.stop()
      self.server_queue[ctx.guild.id] = []
      self.active_servers[ctx.guild.id]['loop'] = False
      await ctx.send('Stop ⏹')

  @commands.command(description='Skip current song')
  async def skip(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    ctx.voice_client.stop()
    
    if len(self.server_queue[ctx.guild.id]) > 0:
      title = self.server_queue[ctx.guild.id][0]
      self.server_queue.pop(0)
      if self.active_server[ctx.guild.id]['loop']:
        self.server_queue[ctx.guild.id].append(title)

    await ctx.send('Song skipped')

  @commands.command(description='Toggle loop')
  async def loop(self, ctx):
    self.active_servers[ctx.guild.id]['loop'] = not self.active_servers[ctx.guild.id]['loop']
    if self.active_servers[ctx.guild.id]['loop']:
      await ctx.send('Songs added to loop')
    else:
      await ctx.send('Songs removed from loop')
    

  @tasks.loop(seconds=1)
  async def queue_check(self):
    for server_id in self.active_servers:
      voice_client, channel, loop, _continue = self.active_servers[server_id].values()

      all_members = [member.name for member in voice_client.channel.members]

      if len(all_members) <= 1  and voice_client.is_playing():
        voice_client.pause()
        await channel.send('All users have left the voice channel. Paused ⏸')
        self.active_servers[server_id]['continue'] = False
        _continue = False
        
      
      if not voice_client.is_playing() and len(self.server_queue[server_id]) > 0 and len(all_members) > 1 and _continue:
        title, url = getUrl(self.server_queue[server_id][0])
        self.server_queue[server_id].pop(0)
        if self.active_servers[server_id]['loop']:
          self.server_queue[server_id].append(title)

        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
          try:
            info = ydl.extract_info(url, download=False)
            url2 = info['formats'][0]['url']
            scource = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            voice_client.play(scource)
            await channel.send(f'Current playing - {title}')
          except:
            await channel.send(f'Error while playing - {title}')
      
  @commands.Cog.listener()
  async def on_command_error(self, ctx, error):
    await ctx.send(error)

  def setup(client):
    client.add_cog(CLI(client))