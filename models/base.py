from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class GuildTextChannel(Base):
    __tablename__ = 'guild_text_channel'
    guild_id = Column(String, primary_key=True)
    text_channel_id = Column(String, nullable=False)

class YoutubeChannel(Base):
    __tablename__ = 'youtube_channels'
    channel_name = Column(String, primary_key=True)

class Reminder(Base):
    __tablename__ = 'reminders'
    guild_id = Column(String, ForeignKey('guild_text_channel.guild_id'), primary_key=True)
    channel_name = Column(String, ForeignKey('youtube_channels.channel_name'), primary_key=True)

class LastStream(Base):
    __tablename__ = 'last_stream'
    channel_name = Column(String, ForeignKey('youtube_channels.channel_name'), primary_key=True)
    stream_link = Column(String)

class LastVideo(Base):
    __tablename__ = 'last_video'
    channel_name = Column(String, ForeignKey('youtube_channels.channel_name'), primary_key=True)
    video_link = Column(String)