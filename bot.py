import asyncio
import logging
import os
import re
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

TOKEN = "8617585421:AAEsSVjavLegxAAiVJFLKnrZ2cP9moYkpbo"
MAX_UPLOAD_MB = 45
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("video-saqla-bot")

SUPPORTED_HOSTS = {
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "instagram.com",
    "tiktok.com",
}


def extract_url(text: str):
    if not text:
        return None

    for match in re.findall(r"https?://[^\s]+", text):
        url = match.strip("()[]<>.,!?\"'")

        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()

            if (
                parsed.scheme in ("http", "https")
                and any(
                    host == domain or host.endswith("." + domain)
                    for domain in SUPPORTED_HOSTS
                )
            ):
                return url

        except ValueError:
            pass

    return None


def download_video(url: str, output_dir: str) -> Path:
    options = {
        "format": (
            "best[ext=mp4][filesize<45M]/"
            "best[filesize<45M]/best[ext=mp4]/best"
        ),
        "outtmpl": str(Path(output_dir) / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 25,
        "retries": 2,
        "fragment_retries": 2,
        "max_filesize": MAX_UPLOAD_MB * 1024 * 1024,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        path = Path(ydl.prepare_filename(info))

        if not path.exists():
            files = [
                item
                for item in Path(output_dir).glob("*")
                if item.is_file()
            ]

            if not files:
                raise FileNotFoundError(
                    "Yuklangan fayl topilmadi."
                )

            path = files[0]

        if path.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
            raise ValueError("Video 45 MB limitidan katta.")

        return path


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    name = (
        user.first_name
        if user and user.first_name
        else "do‘stim"
    )

    await update.effective_message.reply_text(
        f"👋 Assalomu alaykum, {name}!\n\n"
        "📥 VIDEO SAQLA BOT ga xush kelibsiz!\n\n"
        "🎬 YouTube, Instagram yoki TikTok "
        "video havolasini yuboring.\n"
        "⏳ Bot videoni yuklab olishga harakat qiladi.\n\n"
        "ℹ️ Ayrim videolar platforma cheklovlari "
        "sababli yuklanmasligi mumkin."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text(
        "📖 FOYDALANISH YO‘RIQNOMASI\n\n"
        "1️⃣ Video havolasini nusxalang.\n"
        "2️⃣ Havolani botga yuboring.\n"
        "3️⃣ Yuklanishini kuting.\n\n"
        "❗ Faqat kirish huquqingiz bor "
        "videolardan foydalaning."
    )


async def handle_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    url = extract_url(message.text or "")

    if not url:
        await message.reply_text(
            "🔗 YouTube, Instagram yoki TikTok "
            "video havolasini yuboring."
        )
        return

    status = await message.reply_text(
        "⏳ Havola qabul qilindi. Video yuklanmoqda..."
    )

    try:
        async with DOWNLOAD_SEMAPHORE:
            with tempfile.TemporaryDirectory(
                prefix="video_saqla_"
            ) as temp_dir:

                path = await asyncio.to_thread(
                    download_video,
                    url,
                    temp_dir,
                )

                with path.open("rb") as video:
                    await message.reply_video(
                        video=video,
                        caption="✅ Mana siz so‘ragan video! 🎬",
                        supports_streaming=True,
                        read_timeout=120,
                        write_timeout=120,
                        connect_timeout=30,
                    )

        await status.delete()

    except Exception as error:
        logger.exception(
    "Video yuklashda xatolik: %s",
    error,
)

        details = str(error).lower()

        if any(
            word in details
            for word in ("private", "sign in", "login")
        ):
            answer = (
                "❌ Video yopiq yoki login talab qilishi "
                "mumkin. Ochiq havola bilan urinib ko‘ring."
            )

        elif any(
            word in details
            for word in ("filesize", "too large", "45 mb", "limit")
        ):
            answer = (
                "❌ Video 45 MB limitidan katta. "
                "Qisqaroq videoni sinab ko‘ring."
            )

        else:
            answer = (
                "❌ Videoni yuklab bo‘lmadi.\n\n"
                "Havola ochiq ekanini tekshiring va "
                "qayta urinib ko‘ring.\n"
                "Ayrim platformalar yuklashni cheklashi mumkin."
            )

        try:
            await status.edit_text(answer)
        except Exception:
            await message.reply_text(answer)


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN topilmadi. "
            "Hostingdagi Environment Variables bo‘limiga "
            "tokenni kiriting."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_link,
        )
    )

    logger.info("Video Saqla Bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()