# bot.py
import os
import sys
import time
import tempfile
import telebot
from yt_dlp import YoutubeDL
from flask import Flask
from threading import Thread

# ---- BOT TOKEN (must be set as environment variable on the host) ----
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable not set. Set BOT_TOKEN on your host and restart.")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# ---- small Flask keep-alive server (Render expects a service listening on PORT) ----
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port)

# start Flask in background so bot.polling can run in main thread
Thread(target=run_flask, daemon=True).start()

# ---- Helpers & Handlers ----
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Send me an Instagram Reels, YouTube Shorts, or Facebook video link "
        "and I'll download the video for you."
    )

def is_instagram_link(text: str) -> bool:
    return text and ("instagram.com" in text.lower() or "instagr.am" in text.lower())

def is_youtube_shorts_link(text: str) -> bool:
    return text and ("youtube.com/shorts" in text.lower() or "youtu.be" in text.lower())

def is_facebook_link(text: str) -> bool:
    return text and ("facebook.com" in text.lower() or "fb.watch" in text.lower())

@bot.message_handler(func=lambda m: m.text and (
    is_instagram_link(m.text) or is_youtube_shorts_link(m.text) or is_facebook_link(m.text)))
def handle_download(message):
    url = message.text.strip()
    print("Received URL:", url)   # visible in Render logs
    status_msg = bot.reply_to(message, "⏳ Downloading… please wait.")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            ydl_opts = {
                'format': 'mp4/best',
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)

            if not os.path.exists(filepath):
                bot.edit_message_text(
                    "❌ Download failed (file not found).",
                    chat_id=message.chat.id,
                    message_id=status_msg.message_id
                )
                return

            filesize = os.path.getsize(filepath)
            with open(filepath, 'rb') as f:
                if filesize <= 49 * 1024 * 1024:  # under ~49 MB send as video
                    bot.send_video(message.chat.id, f, timeout=180)
                else:
                    bot.send_document(message.chat.id, f, timeout=180)

            bot.edit_message_text(
                "✅ Download complete!",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )

        except Exception as e:
            print("Download error:", str(e))
            bot.edit_message_text(
                f"❌ Error: {str(e)}",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )

@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.reply_to(
        m,
        "Please send a valid Instagram, YouTube Shorts, or Facebook video link."
    )

# ---- Start polling (restart automatically if polling fails) ----
if __name__ == "__main__":
    print("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print("Polling failed, restarting in 5s...", e)
            time.sleep(5)
