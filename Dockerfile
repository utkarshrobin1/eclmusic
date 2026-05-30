FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir pyrogram==2.0.106 TgCrypto==1.2.5 pytgcalls==5.11.0

COPY . .

CMD ["python", "bot.py"]
