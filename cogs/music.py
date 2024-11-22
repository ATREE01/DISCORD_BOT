import discord 
from discord.ext import commands
from discord import app_commands

import os
import asyncio
import datetime

import yt_dlp
from pytube import Playlist

from enum import Enum

class MusicBotState(Enum):
    IDLE = 'idle'
    PLAYING = 'playing'
    SKIPPING = 'skipping'
    PAUSED = 'paused'
    

class Music(commands.Cog, description="Commands for playing music from youtube."):
    def __init__(self, bot):
        self.bot = bot

        self.guild_info = {}
        
        self.YDL_OPTIONS = {
            'format': 'bestaudio',
            'noplaylist': True,
            'quiet': True,
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'outtmpl': './Youtube/%(title)s.%(ext)s',
        }
       
        self.FFMEPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 2',
            'options': '-vn'
        }
        
    def init_guild(self, guild_id):
        self.guild_info[guild_id] = {
            'state': MusicBotState.IDLE,
            'music_queue': [],
            'voice_channel': None,
            'loop': False,
            'music_info': None,
            'music_info_msg': None,
        }
    
    async def search_youtube(self, query):
        try:
            with yt_dlp.YoutubeDL(self.YDL_OPTIONS) as ydl:
                if any(query.startswith(prefix) for prefix in ["https://www.youtube.com/",  "https://youtu.be/", "https://music.youtube.com/"]):
                    info = await asyncio.to_thread(ydl.extract_info, url=query, download=False)   
                else:
                    info = (await asyncio.to_thread(ydl.extract_info, url=f'ytsearch:{query}', download=False))['entries'][0]
            
            duration = info['duration'] if 'duration' in info else 'Live'        
            
            song = {
                'title': info['title'],
                'duration': duration,
                'channel_name': info['channel'],
                'channel_url': info['channel_url'],
                'url': info['webpage_url'],
                'music_url': [_['url'] for _ in info['formats'] if (duration == 'Live' and _.get('resolution') == 'audio only') or  # get the url for live stream
                              (_.get('format_note') == 'medium' and _.get('ext') == 'webm')][0], # get the url for normal video
                'thumbnail': info['thumbnail'],
            }
            return song
        except Exception as e:
            print(e)
            return False
    
    def my_after(self, guild_id, text_channel):
        # if the bot bot is not connected to a voice channel
        if not self.guild_info[guild_id]['voice_channel'].is_connected():
            self.guild_info[guild_id]['state'] = MusicBotState.IDLE
            return 
        
        coro = self.play_next(guild_id, text_channel)
        future = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
    
    async def idle_timer(self, guild_id, text_channel):
        self.guild_info[guild_id]['state'] = MusicBotState.IDLE
        await asyncio.sleep(180)
        if self.guild_info[guild_id]['state'] == MusicBotState.IDLE:
            emb = discord.Embed(title='Idle for too long! Bye Bye~', color=discord.Color.red())
            await text_channel.send(embed = emb)
            await self.guild_info[guild_id]['voice_channel'].disconnect()
            
    async def play_next(self, guild_id, text_channel):
        # only when looping, there is no need to pop the first song
        if self.guild_info[guild_id]['loop'] != True:
            self.guild_info[guild_id]['music_queue'].pop(0)
        try:
            await self.guild_info[guild_id]['music_info_msg'].delete()
            self.guild_info[guild_id]['music_info_msg'] = None
        except:
            pass

        await self.play_music(guild_id, text_channel, self.guild_info[guild_id]['voice_channel'])
    
    def get_playing_info(self, guild_id):
        emb = discord.Embed(title='Now playing 🎵: ', color=discord.Color.blue())
        emb.set_thumbnail(url=self.guild_info[guild_id]['music_info']['thumbnail'])
        emb.add_field(name='Title:', value=f"[{self.guild_info[guild_id]['music_info']['title']}]({self.guild_info[guild_id]['music_info']['url']})", inline=False)
        emb.add_field(name='Channel:', value=f"[{self.guild_info[guild_id]['music_info']['channel_name']}]({self.guild_info[guild_id]['music_info']['channel_url']})")
        emb.add_field(name='Duration:', value='Live' if self.guild_info[guild_id]['music_info']['duration'] == 'Live' else datetime.timedelta(seconds = self.guild_info[guild_id]['music_info']['duration']))
        return emb

    async def play_music(self, guild_id, text_channel, voice_channel):
        while len(self.guild_info[guild_id]['music_queue']) > 0:
            self.guild_info[guild_id]['music_info'] = await self.search_youtube(self.guild_info[guild_id]['music_queue'][0])
            if not self.guild_info[guild_id]['music_info']:
                await text_channel.send(f"Can not play this track \"{self.guild_info[guild_id]['music_queue'][0]}\" skipping to next track.")
                self.guild_info[guild_id]['music_queue'][0].pop(0)
                continue 
            break
        else:
            await self.idle_timer(guild_id, text_channel)
            return
        
        if self.guild_info[guild_id]['voice_channel'] == None or not self.guild_info[guild_id]['voice_channel'].is_connected():
            self.guild_info[guild_id]['voice_channel'] = await voice_channel.connect()
            
        if self.guild_info[guild_id]['voice_channel'] != voice_channel: # if the person using the command is not in the same channel with the bot
            await self.guild_info[guild_id]['voice_channel'].move_to(voice_channel)
        
        self.guild_info[guild_id]['music_info_msg'] = await text_channel.send(embed=self.get_playing_info(guild_id))
        self.guild_info[guild_id]['state'] = MusicBotState.PLAYING
        source = await discord.FFmpegOpusAudio.from_probe(self.guild_info[guild_id]['music_info']['music_url'], **self.FFMEPEG_OPTIONS)   
        self.guild_info[guild_id]['voice_channel'].play(source, after=lambda e: self.my_after(guild_id, text_channel))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # if the bot left the voice channel
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            guild_id = before.channel.guild.id
            self.guild_info[guild_id]['state'] = MusicBotState.IDLE
            if self.guild_info[guild_id]['music_info_msg'] != None:
                await self.guild_info[guild_id]['music_info_msg'].delete()
    
    @app_commands.command(name='play', description='Play music from youtube')
    async def play(self, interaction: discord.Interaction, query: str = None):
        guild_id = interaction.guild_id
        text_channel = interaction.channel
        try: 
            voice_channel = interaction.user.voice.channel
        except:
            await interaction.response.send_message('You must be in a voice channel to use this command.')
            return
        
        if guild_id not in self.guild_info:
            self.init_guild(guild_id)
        
        if query == None:
            if self.guild_info[guild_id]['state'] == MusicBotState.PLAYING:
                await interaction.response.send_message('Music is already playing.')
            elif self.guild_info[guild_id]['state'] == MusicBotState.PAUSED:
                self.guild_info[guild_id]['voice_channel'].resume()
                await interaction.response.send_message('Resume playing music.')
            elif len(self.guild_info[guild_id]['music_queue']): # if the queue is not empty and the bot is not playing
                await interaction.response.send_message('Resume playing music.')
                await self.play_music(guild_id, text_channel, voice_channel)
            else:
                await interaction.response.send_message('No music in the queue.')
        
        elif query != None: # addding music to queue
            if query.startswith("https://www.youtube.com/playlist?list=") or query.startswith("https://music.youtube.com/playlist?list="): # add playlist
                playlist = Playlist(query)
                self.guild_info[guild_id]['music_queue'].extend(playlist)
                await interaction.response.send_message(f"{len(playlist)} songs added to the queue.")
                
            elif query.startswith("https://www.youtube.com/watch?v=") or query.startswith("https://music.youtube.com/watch?v=") and "&list" in query: # a song in playing playlist
                query = query.split('&list')
                self.guild_info[guild_id]['music_queue'].append(query[0])
                await interaction.response.send_message("Song added to the queue.")
                
            else: # single url or keyword
                self.guild_info[guild_id]['music_queue'].append(query)
                await interaction.response.send_message('Query added to the queue.')
        
            if self.guild_info[guild_id]['state'] == MusicBotState.IDLE:
                await self.play_music(guild_id, text_channel, voice_channel)

    @app_commands.command(name='pause', description='Pause the music')
    async def pause(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id  in self.guild_info and self.guild_info[guild_id]['state'] == MusicBotState.PLAYING:
            await interaction.response.send_message('Music paused. ⏸️')
            self.guild_info[guild_id]['voice_channel'].pause()
            self.guild_info[guild_id]['state'] = MusicBotState.PAUSED
            return
        else:
            await interaction.response.send_message('No music is playing.')

    @app_commands.command(name='skip', description='Skip the current song')
    async def skip(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in self.guild_info and self.guild_info[guild_id]['state'] == MusicBotState.PLAYING:
            self.guild_info[guild_id]['voice_channel'].stop()
            self.guild_info[guild_id]['state'] = MusicBotState.SKIPPING
            await interaction.response.send_message('Music skiped. ⏭️')
        else:
            await interaction.response.send_message('No music is playing.')
    
    @app_commands.command(name='jump', description="Jump to a specific song in the queue(except current one).")
    async def jump(self, interaction: discord.Interaction, index: int):
        guild_id = interaction.guild.id
        if guild_id in self.guild_info  and len(self.guild_info[guild_id]['music_queue']) >= index > 1:
            self.guild_info[guild_id]['voice_channel'].stop()
            self.guild_info[guild_id]['music_queue'] = self.guild_info[guild_id]['music_queue'][index - 1:]
            self.guild_info[guild_id]['state'] = MusicBotState.SKIPPING
            await interaction.response.send_message(f'Jumped to number {index} ⏭️')
        else:
            await interaction.response.send_message('Index out of range.')

    @app_commands.command(name='remove', description="Remove a specific song from the queue.")
    async def remove(self, interaction: discord.Interaction, index: int):
        guild_id = interaction.guild.id
        if guild_id in self.guild_info and len(self.guild_info[guild_id]['music_queue']) >= index > 0:
            
            if index == 0:
                self.guild_info[guild_id]['voice_channel'].stop()
                self.guild_info[guild_id]['state'] = MusicBotState.SKIPPING
                
            self.guild_info[guild_id]['music_queue'].pop(index - 1)
            await interaction.response.send_message("Music removed.")
        else:
            await interaction.response.send_message("Index out of range.")

    @app_commands.command(name='loop', description='Change the loop state of the music currently playing.')
    async def loop(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if guild_id in self.guild_info and self.guild_info[guild_id]['state'] == MusicBotState.PLAYING:
            if self.guild_info[guild_id]['loop']:
                await interaction.response.send_message('Stop looping the music.')
            else:
                await interaction.response.send_message('Looping the music.')
            self.guild_info[guild_id]['loop'] = not self.guild_info[guild_id]['loop']
        else:
            await interaction.response.send_message('No music is playing.')
    
    @app_commands.command(name='queue', description='Show the current queue')
    async def queue(self,interaction: discord.Interaction, page: int=1):
        guild_id = interaction.guild.id
        if guild_id not in self.guild_info or len(self.guild_info[guild_id]['music_queue']) == 0: # bug here
            await interaction.response.send_message("No music in the queue.") 
        else:
            await interaction.response.defer()
            emb = discord.Embed(title=f'Music queue Total : {len(self.guild_info[guild_id]['music_queue'])}', color=discord.Color.blue())
            tasks = [self.search_youtube(self.guild_info[guild_id]['music_queue'][i]) for i in range((page-1)*10, min((page)*10, len(self.guild_info[guild_id]['music_queue'])))]
            results = await asyncio.gather(*tasks)
            for (index, song) in enumerate(results):
                try:
                    emb.add_field(name=('Looping' if self.guild_info[guild_id]['loop'] and index != page*10 else ''), value=f"[{index + 1}. {song['title']}]({song['url']})", inline = False)
                except:
                    emb.add_field(name=(' - Looping' if self.guild_info[guild_id]['loop'] and index != page*10 else ''), value=f"({index + 1}) Invalid", inline = False)
            emb.add_field(name=f'Pages: {page}/{len(self.guild_info[guild_id]['music_queue']) // 10 + 1}', value='', inline=False)
            await interaction.followup.send(embed=emb)
    
    @app_commands.command(name='clear', description='Remove the queue except first one.')
    async def clear(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        if guild_id in self.guild_info and len(self.guild_info[guild_id]['music_queue']) > 1:
            self.guild_info[guild_id]['music_queue'] = self.guild_info[guild_id]['music_queue'][:1]
            await interaction.response.send_message('Queue cleared.')
        else:
            await interaction.response.send_message('No music in the queue.')
    
    @app_commands.command(name='leave',description="Leave voice channel")
    async def leave(self,interaction:discord.Interaction):
        guild_id = interaction.guild.id
        await self.guild_id[guild_id]['voice_channel'].disconnect()
        await self.guild_id[guild_id]['state'] == MusicBotState.IDLE
        try:
            await self.guild_info[guild_id]['music_info_msg'].delete()
        except:
            pass
        await interaction.response.send_message("Bye Bye~. 👋")

async def setup(bot):
    await bot.add_cog(Music(bot))