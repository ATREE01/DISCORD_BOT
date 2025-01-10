FROM python:3.12.7-slim-bookworm

WORKDIR /app

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir youtube_reminder_data
RUN echo "{}" > youtube_reminder_data/guild_text_channel.json
RUN echo "{}" > youtube_reminder_data/remind_list.json
RUN echo "{}" > youtube_reminder_data/last_stream.json
RUN echo "{}" > youtube_reminder_data/last_video.json

CMD ["python", "bot.py"]
