import discord
from discord.ext import commands, tasks
import youtube_dl
from .utils import getUrl
from .config import FFMPEG_OPTIONS, YDL_OPTIONS
import os
import json
import random
import tabulate


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
      await ctx.send(f'Bot joined {ctx.author.voice.channel}')
    elif ctx.voice_client.channel != ctx.author.voice.channel:
      await ctx.voice_client.move_to(voice_channel)
      await ctx.send(f'Bot joined {ctx.author.voice.channel}')

    if ctx.guild.id not in self.active_servers:
      self.active_servers[ctx.guild.id] = {
          'voice_client': ctx.voice_client,
          'channel': ctx.channel,
          'loop': False,
          'continue': True,
          'current_playing': '',
          }

    if ctx.guild.id not in self.server_queue:
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
      return

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
    
    await ctx.send('Song skipped')


  @commands.command(description='Toggle loop')
  async def loop(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    self.active_servers[ctx.guild.id]['loop'] = not self.active_servers[ctx.guild.id]['loop']
    if self.active_servers[ctx.guild.id]['loop']:
      await ctx.send('Songs added to loop')
    else:
      await ctx.send('Songs removed from loop')


  @commands.command(description='Repeat current song')
  async def repeat(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    current = self.active_servers[ctx.guild.id]['current_playing']
    self.server_queue[ctx.guild.id].insert(0, current)
    await ctx.send(f'Repeating - {current}')


  @commands.command(description = 'Get all songs of queue')
  async def get_queue(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    all_songs = tabulate.tabulate([(i, title) for i, title in enumerate(self.server_queue[ctx.guild.id])], headers=['ID', 'Title'])

    await ctx.send(all_songs)


  @commands.command(description = 'Pop a song from queue')
  async def pop(self, ctx, song_id):
    try:
      song_id = int(song_id)
    except:
      await ctx.send(f'Invalid song id')
      return

    if song_id < 0 or song_id >= len(self.server_queue[ctx.guild.id]):
      await ctx.send(f'Invalid song id')
      return

    title = self.server_queue[ctx.guild.id][song_id]
    self.server_queue[ctx.guild.id].pop(song_id)
    await ctx.send(f'{title} removed from queue')
    

  @tasks.loop(seconds=1)
  async def queue_check(self):
    for server_id in self.active_servers:
      voice_client = self.active_servers[server_id]["voice_client"]
      channel = self.active_servers[server_id]["channel"]
      loop = self.active_servers[server_id]["loop"]
      _continue = self.active_servers[server_id]["continue"]

      all_members = [member.name for member in voice_client.channel.members]

      if len(all_members) <= 1  and voice_client.is_playing():
        voice_client.pause()
        await channel.send('All users have left the voice channel. Paused ⏸')
        self.active_servers[server_id]['continue'] = False
        _continue = False
        
      
      if not voice_client.is_playing() and len(self.server_queue[server_id]) > 0 and len(all_members) > 1 and _continue:
        title, url = getUrl(self.server_queue[server_id][0])
        self.server_queue[server_id].pop(0)
        if loop:
          self.server_queue[server_id].append(title)

        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
          try:
            info = ydl.extract_info(url, download=False)
            url2 = info['formats'][0]['url']
            scource = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            voice_client.play(scource)
            self.active_servers[server_id]['current_playing'] = title
            await channel.send(f'Current playing - {title}')
          except Exception as e:
            print(e)
            await channel.send(f'Error while playing - {title}')


  @commands.command(description = 'Create new playlist')
  async def create(self, ctx, playlist):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists:
      playlists[server_id] = {}

    if playlist in playlists[server_id]:
      await ctx.send(f'Playlist already exsist - {playlist}')
      return

    playlists[server_id][playlist] = {}
    playlists[server_id][playlist]["songs"] = []
    playlists[server_id][playlist]["created_by"] = ctx.author.name
    await ctx.send(f'Playlist created - {playlist}')

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'),'w') as p:
      json.dump(playlists, p, indent=4)

    
  @commands.command(description = 'Clear playlist')
  async def clear(self, ctx, playlist):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists or playlist not in playlists[server_id]:
      await ctx.send(f'No playlist - {playlist}. Use -create')
      return

    playlists[server_id][playlist]["songs"] = []
    await ctx.send(f'Playlist clear - {playlist}')

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'),'w') as p:
      json.dump(playlists, p, indent=4)


  @commands.command(description = 'Get all playlist')
  async def get_playlists(self, ctx):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists:
      await ctx.send(f'No playlist. Use -create')
      return

    all_songs = tabulate.tabulate([(i, playlist, playlists[server_id][playlist]["created_by"]) for i, playlist in enumerate(playlists[server_id])], headers=['ID', 'Playlist', 'created_by'])

    await ctx.send(all_songs)

  @commands.command(description = 'Add song to a playlist')
  async def add(self, ctx, playlist, *, song):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists or playlist not in playlists[server_id]:
      await ctx.send(f'No playlist - {playlist}. Use -create')
      return

    try:
      title, url = getUrl(song)
    except:
      await ctx.send(f'No song - {song[:30]}...')
      return

    if title in playlists[server_id][playlist]["songs"]:
      await ctx.send(f'{title} already in - {playlist}')
      return

    playlists[server_id][playlist]["songs"].append(title)
    await ctx.send(f'{title} added in - {playlist}')

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'),'w') as p:
      json.dump(playlists, p, indent=4)

 
  @commands.command(description = 'Remove a playist and if song id is provided remove song')
  async def remove(self, ctx, playlist, song_id=-1):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists or playlist not in playlists[server_id]:
      await ctx.send(f'No playlist - {playlist}. Use -create')
      return
      
    try:
      song_id = int(song_id)
    except:
      await ctx.send(f'Invalid song id')
      return

    if song_id == -1:
      del playlists[server_id][playlist]
      await ctx.send(f'Playlist removed - {playlist}')
      
      with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'),'w') as p:
        json.dump(playlists, p, indent=4)
      return

    if song_id < 0 or song_id >= len(playlists[server_id][playlist]["songs"]):
      await ctx.send(f'Invalid song id')
      return

    title = playlists[server_id][playlist]["songs"][song_id]
    playlists[server_id][playlist]["songs"].pop(song_id)
    await ctx.send(f'{title} removed from - {playlist}')

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'),'w') as p:
      json.dump(playlists, p, indent=4)

  
  @commands.command(description = 'Get all songs of playlist')
  async def get_songs(self, ctx, playlist):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists or playlist not in playlists[server_id]:
      await ctx.send(f'No playlist - {playlist}. Use -create')
      return

    all_songs = tabulate.tabulate([(i, title) for i, title in enumerate(playlists[server_id][playlist]["songs"])], headers=['ID', 'Title'])

    await ctx.send(f'Playlist - {playlist}   Created by - {playlists[server_id][playlist]["created_by"]} \n'+all_songs)

  
  @commands.command(description = 'play a playlist')
  async def playlist(self, ctx, playlist):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      playlists = json.load(p)

    server_id = str(ctx.guild.id)

    if server_id not in playlists or playlist not in playlists[server_id]:
      await ctx.send(f'No playlist - {playlist}. Use -create')
      return

    await self.join(ctx)
    self.active_servers[ctx.guild.id]['continue'] = True

    self.server_queue[ctx.guild.id] = playlists[server_id][playlist]["songs"]
    await ctx.send(f'Added to queue - {playlist}')


  @commands.command(description = 'shuffle queue')
  async def shuffle(self, ctx):
    if ctx.voice_client is None:
      await ctx.send('Bot is not in a voice channel')
      return

    random.shuffle(self.server_queue[ctx.guild.id])
    await ctx.send(f'Queue shuffled')


  @commands.command(hidden=True)
  async def log_playlists(self, ctx):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json')) as p:
      print(p.read())
  
  
  @commands.command(hidden=True)
  async def load_playlists(self, ctx, *, json_data):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playlists.json'), 'w') as p:
      p.write(json_data)


  @commands.Cog.listener()
  async def on_command_error(self, ctx, error):
    await ctx.send(error)


  def setup(client):
    client.add_cog(CLI(client))