import asyncio
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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
MAX_VIDEO_SIZE = 45 * 1024 * 1024
DOWNLOAD_LIMIT = asyncio.Semaphore(2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_supported_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()

        return parsed.scheme in ("http", "https") and (
            domain == "youtu.be"
            or domain == "youtube.com"
            or domain.endswith(".youtube.com")
            or domain == "youtube-nocookie.com"
            or domain.endswith(".youtube-nocookie.com")
            or domain == "instagram.com"
            or domain.endswith(".instagram.com")
            or domain == "tiktok.com"
            or domain.endswith(".tiktok.com")
        )
    except ValueError:
        return False


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

    path = Path(filename)

    if not path.exists():
        candidates = list(Path(temp_dir).glob("video.*"))
        if not candidates:
            raise FileNotFoundError("Video fayli topilmadi.")
        path = candidates[0]

    return path


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    name = user.first_name if user and user.first_name else "do‘stim"

    await update.message.reply_text(
        f"👋 Assalomu alaykum, {name}!\n\n"
        "📥 VIDEO SAQLA BOT ga xush kelibsiz!\n\n"
        "🎬 YouTube, Instagram yoki TikTok videosini saqlamoqchimisiz?\n"
        "🔗 Video havolasini yuboring — bot uni yuklab olishga harakat qiladi."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(
        "📥 VIDEO SAQLA BOT — FOYDALANISH YO‘RIQNOMASI\n\n"
        "1️⃣ YouTube, Instagram yoki TikTok videosining havolasini nusxalang.\n"
        "2️⃣ Havolani shu botga yuboring.\n"
        "3️⃣ Bot videoni yuklab olishga harakat qiladi.\n"
        "4️⃣ Tayyor bo‘lsa, videoni telefoningizga saqlashingiz mumkin.\n\n"
        "📌 Ayrim videolar platforma cheklovlari sababli yuklanmasligi mumkin."
    )


async def download_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not is_supported_url(url):
        await update.message.reply_text(
            "Iltimos, YouTube, Instagram yoki TikTok havolasini yuboring."
        )
        return

    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower()

    # YouTube havolasidan video ID ni tekshirish.
    if (
        domain in ("youtube.com", "youtu.be")
        or domain.endswith(".youtube.com")
    ):
        query = parse_qs(parsed.query)
        video_id = None

        if domain == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0] or None
        elif parsed.path == "/watch":
            video_id = (query.get("v") or [None])[0]
        elif parsed.path.startswith(("/shorts/", "/live/", "/embed/")):
            parts = parsed.path.strip("/").split("/")
            if len(parts) > 1:
                video_id = parts[1]

        if not video_id:
            await update.message.reply_text(
                "❌ YouTube havolasidan video aniqlanmadi. "
                "Iltimos, to‘liq video havolasini yuboring."
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
                path = await asyncio.to_thread(
                    download_sync,
                    url,
                    temp_dir,
                )

                if path.stat().st_size > MAX_VIDEO_SIZE:
                    await status.edit_text(
                        "❌ Video 45 MB dan katta. "
                        "Iltimos, kichikroq video yuboring."
                    )
                    return

                with path.open("rb") as video:
                    await update.message.reply_video(
                        video=video,
                        caption="✅ Video tayyor!",
                    )

            await status.delete()

        except yt_dlp.utils.DownloadError as exc:
            logger.warning("Video yuklash xatosi: %s", exc)
            error = str(exc).lower()

            if (
                "sign in to confirm" in error
                or "not a bot" in error
            ):
                reply = (
                    "❌ YouTube videoni olish uchun tasdiqlashni talab qildi. "
                    "Boshqa ochiq videoni sinab ko‘ring."
                )
            elif "unavailable" in error or "private video" in error:
                reply = (
                    "❌ Bu video mavjud emas yoki yopiq. "
                    "Iltimos, boshqa havola yuboring."
                )
            else:
                reply = (
                    "❌ Videoni yuklab bo‘lmadi. Havolani tekshirib, "
                    "qayta urinib ko‘ring."
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