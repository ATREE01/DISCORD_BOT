import os
import asyncio
import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import discord
from discord.ext import tasks, commands
from discord import app_commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models.base import Base, GuildTextChannel, YoutubeChannel, Reminder, LastStream, LastVideo

class YoutubeReminder(commands.Cog, description="Commands for youtube remineder"):
    def __init__(self, bot):
        self.bot = bot
        
        self.BASEURL = "https://www.youtube.com/@"
        self.BASEURL2= "https://youtube.com/@"
        self.remind_before_min = 30
        
        self.session = self.init_database()
        self.service = Service(ChromeDriverManager().install())   
        self.chrome_options = self.init_chrome_option(Options())
        self.dectect_update.start()
    
    def init_chrome_option(self, options=Options):     
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument('--log-level=3')    
        return options
        
    def init_database(self):
        connection_string = f'postgresql://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("POSTGRES_DB")}'
        engine = create_engine(connection_string, client_encoding='utf-8')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        return Session()
    
    @app_commands.command(name='set_channel', description="Set this channel for remind message")
    async def set_channel(self, interaction:discord.Interaction):
        text_channel_id = interaction.channel.id
        guild_id = interaction.guild_id
        
        guild_channel = self.session.query(GuildTextChannel).filter_by(guild_id=guild_id).first()
        if guild_channel:
            guild_channel.text_channel_id = text_channel_id
        else:
            guild_channel = GuildTextChannel(guild_id=guild_id, text_channel_id=text_channel_id)
            self.session.add(guild_channel)
        
        self.session.commit()
        await interaction.response.send_message("Setting complete.")
    
    @app_commands.command(name="add_youtube_channel", description="Add youtube channel you want to receive remind.")
    @app_commands.describe(channel_url = "e.g. \"https://www.youtube.com/@*channel_name*\"")
    async def add_channel(self, interaction: discord.Interaction, channel_url: str ):
        guild_id = interaction.guild_id
        
        if not self.session.query(GuildTextChannel).filter_by(guild_id=guild_id).first():
            await interaction.response.send_message("Haven't set the channel for remind. Must use \"set_channel\" first.")
            return

        if (not channel_url.startswith(self.BASEURL)) and (not channel_url.startswith(self.BASEURL2)):
            await interaction.response.send_message("Please check your URL and try again.")
            return

        youtube_channel_name = channel_url.split('/')[-1]
        if youtube_channel_name.startswith('@'):
            youtube_channel_name = youtube_channel_name[1:]
        
        youtube_channel = self.session.query(YoutubeChannel).filter_by(channel_name=youtube_channel_name).first()
        if not youtube_channel:
            youtube_channel = YoutubeChannel(channel_name=youtube_channel_name)
            self.session.add(youtube_channel)

        reminder = Reminder(guild_id=guild_id, channel_name=youtube_channel_name)
        try:
            self.session.add(reminder)
            self.session.commit()
            await interaction.response.send_message("Channel added successfully.")
        except IntegrityError:
            self.session.rollback()
            await interaction.response.send_message("Channel already existed.")
                  
    @app_commands.command(name="show_remind_list", description="Show youtube channel in remind list.")
    async def show_remind_list(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        emb = discord.Embed(title='List of channel to be remind.', color=discord.Color.blue())
        
        reminders = self.session.query(Reminder).filter_by(guild_id=guild_id).all()

        if not reminders:
            emb.add_field(name='You havent\'t add any channel yet!', value='', inline=False)
        else:
            for reminder in reminders:
                emb.add_field(name=f"`{reminder.channel_name}`", value='', inline=False)
        
        await interaction.response.send_message(embed = emb)        
        
    @app_commands.command(name="remove_youtube_channel", description="Remove channel setted for remind.") 
    @app_commands.describe(name="e.g. @\"channelname\"")
    async def Remove_Youtube(self, interaction: discord.Interaction, name: str):
        guild_id = interaction.guild_id
        channel_name = name.strip()
        if channel_name.startswith('@'):
            channel_name = channel_name[1:]
            
        reminder = self.session.query(Reminder).filter_by(guild_id=guild_id, channel_name=channel_name).first()
        if reminder:
            self.session.delete(reminder)
            self.session.commit()
            await interaction.response.send_message("Succellfully remove channel.")
        else:
            await interaction.response.send_message("Please check the name and try again.")
    
    async def scrawler(self, driver, channel: str):
        # remind for stream
        url_stream = self.BASEURL + f'{channel}/streams'
        driver.get(url_stream)
        await asyncio.sleep(0.8)
        
        channel_name_element = driver.find_element(By.XPATH, "//*[@id='text']")
        channel_name = channel_name_element.text
        streams = driver.find_elements(By.XPATH, "//*[@id='contents']/ytd-rich-item-renderer")
        remind_stream = None
        
        now_date = datetime.date.today().strftime("%Y/%#m/%#d")
        now_time = [datetime.datetime.now().hour, datetime.datetime.now().minute]
        for stream in streams:
            if stream.text[0: 4] == '即將直播':
                stream_time_element = stream.find_elements(By.CLASS_NAME, "inline-metadata-item.style-scope.ytd-video-meta-block")[-1]
                stream_time = stream_time_element.text
                live_date = stream_time.split('：')[1].split(' ')[0]
                if live_date == now_date:
                    live_time = [0, int(stream_time[-2: ])]
                    if stream_time[-5].isdigit():
                        live_time[0] = int(stream_time[-5 : -3])
                    else:
                        live_time[0] = int(stream_time[-4 : -3])
                    if (live_time[0] * 60 + live_time[1]) -  (now_time[0] * 60 + now_time[1]) <= self.remind_before_min :
                        remind_stream = stream
            else:
                break
        if remind_stream != None:
            isSuccess = True
            try:
                title_element = remind_stream.find_element(By.CLASS_NAME, "yt-simple-endpoint.focus-on-expand.style-scope.ytd-rich-grid-media")
                title = title_element.text
                link_element = remind_stream.find_element(By.CLASS_NAME, "yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail")
            except Exception:
                print("ERROR!")
                isSuccess = False
            
            last_stream = self.session.query(LastStream).filter_by(channel_name=channel).first()
            if isSuccess and (not last_stream or link != last_stream.stream_link):
                if not last_stream:
                    last_stream = LastStream(channel_name=channel, stream_link=link)
                    self.session.add(last_stream)
                else:
                    last_stream.stream_link = link
                self.session.commit()

                reminders = self.session.query(Reminder).filter_by(channel_name=channel).all()
                for reminder in reminders:
                    guild_channel = self.session.query(GuildTextChannel).filter_by(guild_id=reminder.guild_id).first()
                    try:
                        await text_channel.send(f"**New steam at {live_time[0]} : {live_time[1]:0>2}**\n{channel_name} has a new stream: \n {title}  !\n{link} ")
                    except Exception:
                        print("ERROR!")
                    
        #remind for video          
        url_video = self.BASEURL + f'{channel}/videos'
        driver.get(url_video)
        await asyncio.sleep(0.8)
        lastest_video_element =  driver.find_element(By.XPATH, "//*[@id=\"contents\"]/ytd-rich-item-renderer[1]")
        link_element = lastest_video_element.find_element(By.CLASS_NAME, "yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail")
        link = link_element.get_attribute("href")
        
        last_video = self.session.query(LastVideo).filter_by(channel_name=channel).first()
        if (not last_video or link != last_video.video_link) and last_video and last_video.video_link != None:
            reminders = self.session.query(Reminder).filter_by(channel_name=channel).all()
            for reminder in reminders:
                guild_channel = self.session.query(GuildTextChannel).filter_by(guild_id=reminder.guild_id).first()
                text_channel = self.bot.get_channel(guild_channel.text_channel_id)
                await text_channel.send(f"**Video reminder**\n {channel_name} upload a new video {link}")
                
        if not last_video:
            last_video = LastVideo(channel_name=channel, video_link=link)
            self.session.add(last_video)
        else:
            last_video.video_link = link
        self.session.commit()


    @tasks.loop(minutes = 15)  
    async def dectect_update(self):
        print(datetime.datetime.now(), "Start checking update")
        driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
        
        channels = [c.channel_name for c in self.session.query(YoutubeChannel).all()]
        
        for channel in channels:
            await self.scrawler(driver, channel)
        driver.close()
            
    @dectect_update.before_loop
    async def before_detect(self):
        await self.bot.wait_until_ready()
        
async def setup(bot):
    await bot.add_cog(YoutubeReminder(bot))