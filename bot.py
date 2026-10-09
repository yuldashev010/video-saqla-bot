
import os
import re
import asyncio
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

ALLOWED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "tiktok.com",
}

@app.route("/")
def home():
    return "Video bot ishlayapti!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 👋\n"
        "Men video yuklash botiman.\n\n"
        "YouTube, TikTok yoki Instagram videosining "
        "havolasini yubor.\n\n"
        "/help — yordam"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ishlatish:\n"
        "1. Video havolasini nusxala.\n"
        "2. Botga yubor.\n"
        "3. Video tayyor bo‘lishini kut.\n\n"
        "Faqat o‘zing foydalanishga ruxsating bor "
        "videolarni yukla."
    )

def valid_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme == "https"
            and any(
                host == domain or host.endswith("." + domain)
                for domain in ALLOWED_DOMAINS
            )
        )
    except Exception:
        return False

def download_video(url, folder):
    options = {
        "format": "best[ext=mp4][filesize<45M]/best[filesize<45M]",
        "outtmpl": str(Path(folder) / "video.%(ext)s"),
        "noplaylist": True,
        "max_filesize": 45 * 1024 * 1024,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    files = list(Path(folder).glob("video.*"))
    if not files:
        raise ValueError("Video fayli topilmadi.")

    return files[0]

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    match = re.search(r"https://[^\s]+", url)
    if not match:
        await update.message.reply_text("Iltimos, video havolasini yubor.")
        return

    url = match.group(0).rstrip(".,)")
    if not valid_url(url):
        await update.message.reply_text(
            "Bu havola qo‘llab-quvvatlanmaydi. "
            "YouTube, TikTok yoki Instagram havolasini yubor."
        )
        return

    status = await update.message.reply_text("⏳ Video yuklanmoqda...")

    try:
        with tempfile.TemporaryDirectory() as folder:
            file_path = await asyncio.to_thread(
                download_video, url, folder
            )

            if file_path.stat().st_size > 45 * 1024 * 1024:
                raise ValueError("Video hajmi juda katta.")

            with file_path.open("rb") as video:
                await update.message.reply_video(
                    video=video,
                    caption="✅ Video tayyor!"
                )

        await status.delete()

    except Exception:
        await status.edit_text(
            "❌ Videoni yuklab bo‘lmadi. "
            "Havolani tekshir yoki boshqa video yubor."
        )

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN sozlanmagan.")

    bot = Application.builder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("help", help_command))
    bot.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)
    )
    bot.run_polling()

if __name__ == "__main__":
    import threading

    threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=int(os.environ.get("PORT", 10000))
        ),
        daemon=True
    ).start()

    main()
  
