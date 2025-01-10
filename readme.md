# Discord Bot Project

## Introduction
This project is a custom Discord bot designed to enhance the user experience on your Discord server. The bot is built using Python and the [discord.py](https://discordpy.readthedocs.io/en/stable/) library.

## Features
- **Custom Commands**: Responds to user-defined commands.
- **Music Playback**: Plays music from youtube.
- **Youtube Reminder**: Send notification on new video or stream.
- **Image Downloader**: Download Image from Instagram or Twitter.

##  Reminder

Need to create a directory at root folder and create the follwoing json file in it.
And Remember to write `{}` in the file. This is for the youtube reminder.
```
|  
└─── youtube_reminder_data
    ├─ guild_text_channel.json
    ├─ last_stream.json
    ├─ last_video.json
    └─ remind_list.json
```

## Local Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/ATREE01/DISCORD_BOT.git
    ```
2. Navigate to the project directory:
    ```bash
    cd discord-bot
    ```
3. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4. Ensure you have `FFmpeg` installed on your system, as it is required for music playback.

## Docker Deploy
1. 
    ```bash
    docker compose up 
    ```

## Configuration
1. Create a `.env` file in the project directory and add your Discord bot token:
    ```env
    TOKEN=your_bot_token_here
    ```

## Usage
Start the bot by running:
```bash
python bot.py
```
