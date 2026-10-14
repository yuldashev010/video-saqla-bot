import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Bir vaqtda ko‘pi bilan 2 ta video yuklanadi.
DOWNLOAD_LIMIT = asyncio.Semaphore(2)
MAX_VIDEO_SIZE = 45 * 1024 * 1024


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    ism = user.first_name if user and user.first_name else "do‘stim"

    await update.message.reply_text(
        f"👋 Assalomu alaykum, {ism}!\n\n"
        "📥 VIDEO SAQLA BOT ga xush kelibsiz!\n\n"
        "🎬 YouTube, Instagram yoki TikTok videosini saqlamoqchimisiz?\n"
        "🔗 Video havolasini yuboring — bot uni yuklab olishga harakat qiladi."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "📥 VIDEO SAQLA BOT — FOYDALANISH YO‘RIQNOMASI\n\n"
        "Assalomu alaykum! 👋\n\n"
        "1️⃣ YouTube, TikTok yoki Instagram videosining havolasini nusxalang.\n"
        "2️⃣ Havolani shu botga yuboring.\n"
        "3️⃣ Bot videoni yuklab olishga harakat qiladi.\n"
        "4️⃣ Video tayyor bo‘lsa, uni telefoningizga saqlashingiz mumkin.\n\n"
        "📌 Ayrim videolar platforma cheklovlari sababli yuklanmasligi mumkin."
    )


def download_sync(url: str, temp_dir: str) -> Path:
    options = {
        "outtmpl": str(Path(temp_dir) / "video.%(ext)s"),
        "format": "best[filesize<45M]/best[filesize_approx<45M]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    file_path = Path(filename)

    if not file_path.exists():
        candidates = list(Path(temp_dir).glob("video.*"))
        if not candidates:
            raise FileNotFoundError("Video fayli topilmadi.")
        file_path = candidates[0]

    return file_path


async def download_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()
    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower()

    allowed = (
        domain == "youtu.be"
        or domain == "youtube.com"
        or domain.endswith(".youtube.com")
        or domain == "instagram.com"
        or domain.endswith(".instagram.com")
        or domain == "tiktok.com"
        or domain.endswith(".tiktok.com")
    )

    if parsed.scheme not in ("https", "http") or not allowed:
        await update.message.reply_text(
            "Iltimos, YouTube, Instagram yoki TikTok havolasini yuboring."
        )
        return

    status = await update.message.reply_text(
        "⏳ Havolangiz qabul qilindi. Yuklash navbatiga qo‘shilmoqda..."
    )

    async with DOWNLOAD_LIMIT:
        try:
            await status.edit_text(
                "⏳ Video yuklanmoqda. Iltimos, kuting..."
            )

            with tempfile.TemporaryDirectory(
                prefix="video_saqla_"
            ) as temp_dir:

                file_path = await asyncio.to_thread(
                    download_sync,
                    url,
                    temp_dir,
                )

                if file_path.stat().st_size > MAX_VIDEO_SIZE:
                    await status.edit_text(
                        "❌ Video 45 MB dan katta. "
                        "Iltimos, kichikroq video yuboring."
                    )
                    return

                with file_path.open("rb") as video:
                    await update.message.reply_video(
                        video=video,
                        caption="✅ Video tayyor!",
                    )

            await status.delete()

        except yt_dlp.utils.DownloadError as e:
            logger.warning("Video yuklash xatosi: %s", e)
            error_text = str(e).lower()

            if (
                "sign in to confirm" in error_text
                or "not a bot" in error_text
            ):
                reply = (
                    "❌ YouTube videoni olish uchun tasdiqlashni talab qildi. "
                    "Iltimos, boshqa ochiq videoni sinab ko‘ring."
                )
            elif (
                "video unavailable" in error_text
                or "is unavailable" in error_text
            ):
                reply = (
                    "❌ Bu video mavjud emas yoki unga kirish cheklangan. "
                    "Iltimos, boshqa havola yuboring."
                )
            else:
                reply = (
                    "❌ Videoni yuklab bo‘lmadi. "
                    "Havolani tekshirib, qayta urinib ko‘ring."
                )

            await status.edit_text(reply)

        except Exception:
            logger.exception("Video bilan ishlashda xatolik")

            try:
                await status.edit_text(
                    "❌ Xatolik yuz berdi. "
                    "Iltimos, birozdan so‘ng qayta urinib ko‘ring."
                )
            except TelegramError:
                pass


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN Environment Variable sozlanmagan"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            download_video,
        )
    )

    logger.info("VIDEO SAQLA BOT ishga tushmoqda...")
    app.run_polling()


if __name__ == "__main__":
    main()