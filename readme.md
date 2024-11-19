# Discord Bot Project

## Introduction
This project is a custom Discord bot designed to enhance the user experience on your Discord server. The bot is built using Python and the [discord.py](https://discordpy.readthedocs.io/en/stable/) library.

## Features
- **Custom Commands**: Responds to user-defined commands.
- **Music Playback**: Plays music from youtube.

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
