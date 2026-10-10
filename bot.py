
import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

TOKEN = os.getenv("BOT_TOKEN")
app = Flask(__name__)

@app.route("/")
def home():
    return "Video yukla bot ishlayapti!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Video yukla botga xush kelibsiz!\n\n"
        "YouTube, TikTok yoki Instagram video havolasini yuboring."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Foydalanish:\n"
        "1. Videoning havolasini nusxalang.\n"
        "2. Shu yerga yuboring.\n"
        "3. Video tayyor bo‘lishini kuting.\n\n"
        "Eslatma: barcha havolalar ham yuklanmasligi mumkin."
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    url = message.text.strip()

    if not url.startswith(("https://", "http://")):
        await message.reply_text("❌ Iltimos, to‘liq video havolasini yuboring.")
        return

    status = await message.reply_text("⏳ Video tekshirilmoqda, kuting...")

    filename = None
    try:
        options = {
            "format": "best[ext=mp4]/best",
            "outtmpl": "/tmp/video_%(id)s.%(ext)s",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 25,
            "retries": 2,
            "max_filesize": 45 * 1024 * 1024,
        }

        def get_video():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await asyncio.to_thread(get_video)

        if not os.path.isfile(filename):
            await status.edit_text("❌ Video fayli topilmadi.")
            return

        if os.path.getsize(filename) > 45 * 1024 * 1024:
            await status.edit_text("❌ Video 45 MB dan katta.")
            return

        await status.edit_text("📤 Video Telegramga yuborilmoqda...")

        with open(filename, "rb") as video:
            await message.reply_video(
                video=video,
                caption="✅ Video tayyor!"
            )

        await status.delete()

    except Exception:
        logging.exception("Video yuklashda xatolik")
        await status.edit_text(
            "❌ Videoni yuklab bo‘lmadi.\n\n"
            "Havolani tekshiring yoki boshqa video yuboring. "
            "Ayrim videolar login talab qilishi yoki cheklangan bo‘lishi mumkin."
        )

    finally:
        if filename and os.path.isfile(filename):
            try:
                os.remove(filename)
            except OSError:
                pass

async def post_init(application: Application):
    await application.bot.set_my_commands([
        ("start", "Botni ishga tushirish"),
        ("help", "Yordam"),
    ])

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN muhit o‘zgaruvchisiga kiritilmagan")

    Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )
    application.run_polling()

if __name__ == "__main__":
    main()
      
