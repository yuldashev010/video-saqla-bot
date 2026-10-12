import os
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ism = user.first_name if user and user.first_name else "do‘stim"

    await update.message.reply_text(
        f"👋 Assalomu alaykum, {ism}!\n\n"
        "📥 VIDEO SAQLA BOT ga xush kelibsiz!\n\n"
        "🎬 YouTube, Instagram yoki TikTok videosini saqlamoqchimisiz?\n"
        "🔗 Shunchaki video havolasini yuboring — qolganini bot bajaradi!"
    )




async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📥 VIDEO SAQLA BOT — FOYDALANISH YO‘RIQNOMASI\n\n"
        "Assalomu alaykum! 👋 Botimizga xush kelibsiz!\n\n"
        "🎬 Botdan qanday foydalaniladi?\n\n"
        "1️⃣ YouTube, TikTok yoki Instagram’dan video havolasini nusxalang.\n"
        "2️⃣ Havolani shu botga yuboring.\n"
        "3️⃣ Bot videoni yuklab olishga harakat qiladi.\n"
        "4️⃣ Video tayyor bo‘lsa, uni telefoningizga saqlab olishingiz mumkin.\n\n"
        "📌 Misol:\n"
        "Havolani yuboring — bot uni qayta ishlaydi."
    )



async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    domain = urlparse(url).netloc.lower().split(":")[0]
    allowed = (
        domain == "youtu.be"
        or domain.endswith(".youtube.com")
        or domain == "youtube.com"
        or domain == "instagram.com"
        or domain.endswith(".instagram.com")
        or domain == "tiktok.com"
        or domain.endswith(".tiktok.com")
    )

    if not url.startswith(("https://", "http://")) or not allowed:
        await update.message.reply_text("Iltimos, YouTube, Instagram yoki TikTok havolasini yubor.")
        return

    msg = await update.message.reply_text("⏳ Video yuklanmoqda...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            options = {
                "outtmpl": str(Path(temp_dir) / "video.%(ext)s"),
                "format": "best[filesize<45M]/best",
                "max_filesize": 45 * 1024 * 1024,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

            file_path = Path(filename)
            if not file_path.exists():
                candidates = list(Path(temp_dir).glob("video.*"))
                if not candidates:
                    raise FileNotFoundError("Video fayli topilmadi")
                file_path = candidates[0]

            if file_path.stat().st_size > 45 * 1024 * 1024:
                await msg.edit_text("Video 45 MB dan katta. Boshqa video yubor.")
                return

            with file_path.open("rb") as video:
                await update.message.reply_video(
                    video=video,
                    caption="✅ Tayyor!"
                )

            await msg.delete()

    except Exception:
        logger.exception("Video yuklashda xatolik")
        await msg.edit_text(
            "❌ Videoni yuklay olmadim. Havola ishlashini tekshir; "
            "video yopiq yoki sayt tomonidan cheklangan bo‘lishi mumkin."
        )


def main():
    if not TOKEN:
        raise RuntimeError("Render'da BOT_TOKEN Environment Variable sozlanmagan")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, download_video)
    )

    logger.info("Bot ishga tushmoqda...")
    app.run_polling()


if __name__ == "__main__":
    main()
