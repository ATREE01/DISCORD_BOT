import os
import asyncio
import datetime
import logging

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

logger = logging.getLogger(__name__)

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
        text_channel_id = str(interaction.channel.id)
        guild_id = str(interaction.guild_id)
        
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
        guild_id = str(interaction.guild_id)
        
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
            self.session.commit()

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
            emb.add_field(name='You haven\'t add any channel yet!', value='', inline=False)
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
    
    async def _send_notifications(self, channel_name, channel, message):
        """Send notifications to all subscribed channels."""
        reminders = self.session.query(Reminder).filter_by(channel_name=channel).all()
        for reminder in reminders:
            guild_channel = self.session.query(GuildTextChannel).filter_by(guild_id=str(reminder.guild_id)).first()
            text_channel = self.bot.get_channel(int(guild_channel.text_channel_id))
            try:
                await text_channel.send(message)
            except Exception as e:
                logger.error(f"Failed to send message to channel {guild_channel.text_channel_id}: {e}")
    
    async def _update_content_and_notify(self, content_type, channel, channel_name, link, extra_data=None):
        """Update database and send notifications if content is new."""
        last_entry = None
        if content_type == "stream":
            last_entry = self.session.query(LastStream).filter_by(channel_name=channel).first()
            if not last_entry:
                last_entry = LastStream(channel_name=channel, stream_link=link)
                self.session.add(last_entry)
            elif link == last_entry.stream_link:
                return  # Not a new stream
            else:
                last_entry.stream_link = link
                
            title = extra_data.get("title", "")
            live_time = extra_data.get("live_time", [0, 0])
            message = f"**New steam at {live_time[0]} : {live_time[1]:0>2}**\n{channel_name} has a new stream: \n {title}!\n{link} "
             
        elif content_type == "video":
            last_entry = self.session.query(LastVideo).filter_by(channel_name=channel).first()
            if last_entry:
                logger.info(f"Checking last video for channel {channel}: {last_entry.video_link}")
                logger.info(f"New video link: {link}")
                logger.info(f"Whether is same video: {last_entry.video_link == link}")

            if not last_entry:
                last_entry = LastVideo(channel_name=channel, video_link=link)
                self.session.add(last_entry)
            elif not last_entry.video_link or link == last_entry.video_link:
                last_entry.video_link = link
                return  # Not a new video
            else:
                last_entry.video_link = link
                
            message = f"**Video reminder**\n {channel_name} upload a new video \n{link}"
        
        self.session.commit()
        await self._send_notifications(channel_name, channel, message)
        
    async def scrawler(self, driver, channel: str):
        try:
            # Get channel name (common for both stream and video)
            url_stream = self.BASEURL + f'{channel}/streams'
            driver.get(url_stream)
            await asyncio.sleep(0.8)
            
            try:
                channel_name_element = driver.find_element(By.XPATH, "//*[@id='page-header']/yt-page-header-renderer/yt-page-header-view-model/div/div[1]/div/yt-dynamic-text-view-model")
                channel_name = channel_name_element.text
            except Exception as e:
                logger.warning(f"Could not find channel name for {channel}: {e}")
                channel_name = channel  # Fallback to the channel ID
            
            # Process stream
            now_date = datetime.date.today().strftime("%Y/%#m/%#d")
            now_time = [datetime.datetime.now().hour, datetime.datetime.now().minute]
            
            try:
                latest_stream_element = driver.find_element(By.XPATH, "//*[@id=\"contents\"]/ytd-rich-item-renderer[1]")
                if '正在等候' in latest_stream_element.text:
                    stream_time_element = latest_stream_element.find_elements(By.CLASS_NAME, "inline-metadata-item.style-scope.ytd-video-meta-block")[-1]
                    stream_time = stream_time_element.text
                    live_date = stream_time.split('：')[1].split(' ')[0]
                    if live_date == now_date:
                        live_time = [0, int(stream_time[-2:])]
                        if stream_time[-5].isdigit():
                            live_time[0] = int(stream_time[-5:-3])
                        else:
                            live_time[0] = int(stream_time[-4:-3])
                        if (live_time[0] * 60 + live_time[1]) - (now_time[0] * 60 + now_time[1]) <= self.remind_before_min:
                            title = latest_stream_element.find_element(By.CLASS_NAME, "yt-simple-endpoint.focus-on-expand.style-scope.ytd-rich-grid-media").text
                            link = latest_stream_element.find_element(By.CLASS_NAME, "yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail").get_attribute("href")
                            await self._update_content_and_notify("stream", channel, channel_name, link, {"title": title, "live_time": live_time})
            except Exception as e:
                logger.warning(f"Error processing stream for {channel}: {e}")
                        
            # Process video          
            try:
                url_video = self.BASEURL + f'{channel}/videos'
                driver.get(url_video)
                await asyncio.sleep(0.8)
                
                latest_video_element = driver.find_element(By.XPATH, "//*[@id=\"contents\"]/ytd-rich-item-renderer[1]")
                link_element = latest_video_element.find_element(By.CLASS_NAME, "yt-simple-endpoint.inline-block.style-scope.ytd-thumbnail")
                link = link_element.get_attribute("href").split('&pp=')[0]
                await self._update_content_and_notify("video", channel, channel_name, link)
            except Exception as e:
                logger.warning(f"Error processing video for {channel}: {e}")
        except Exception as e:
            logger.error(f"Fatal error scraping channel {channel}: {e}")


    @tasks.loop(minutes = 15)  
    async def dectect_update(self):
        logger.info(f"{datetime.datetime.now()} Start checking update")
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