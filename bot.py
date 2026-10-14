import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
import yt_dlp

# Loglarni yoqish
logging.basicConfig(level=logging.INFO)

# Token va Admin ID ni shu yerga yozing
TOKEN = "8617585421:AAGGXyKGNI7q83sjPugW0kqtqZ0x--P-aAQ"
ADMIN_ID = @Yuldawev_010  # O'zingizning Telegram ID raqamingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ==================== BAZA BILAN ISHLASH ====================
conn = sqlite3.connect("bot_users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    request_count INTEGER DEFAULT 0
)
"""
)
conn.commit()


def increment_user_requests(user_id: int):
  cursor.execute(
      """
        INSERT INTO users (user_id, request_count) 
        VALUES (?, 1)
        ON CONFLICT(user_id) DO UPDATE SET request_count = request_count + 1
    """,
      (user_id,),
  )
  conn.commit()


# ==================== START BUYRUG'I ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
  user_id = message.from_user.id
  name = message.from_user.first_name  # Foydalanuvchining ismi

  cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
  result = cursor.fetchone()

  if not result:
    cursor.execute(
        "INSERT INTO users (user_id, request_count) VALUES (?, 0)", (user_id,)
    )
    conn.commit()

  # Siz so'ragandek: "Assalomu alaykum" va ismi bilan
  await message.answer(
      f"Assalomu alaykum, **{name}**! 👋\n\n"
      "Menga Instagram, YouTube yoki TikTok havolasini yuboring.\n"
      "Men sizga videoni hamda undagi musiqani topib beraman!"
  )


# ==================== SANOQ (Faqat Admin uchun) ====================
@dp.message(F.text.lower() == "sanoq")
async def show_sanoq(message: Message):
  if message.from_user.id == ADMIN_ID:
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(request_count) FROM users")
    total_requests = cursor.fetchone()[0] or 0

    await message.answer(
        f"📊 **BOT SANOQLARI:**\n\n"
        f"👤 Jami foydalanuvchilar: **{total_users} ta**\n"
        f"📥 Jami yuklab olingan medialar: **{total_requests} marta**"
    )


# ==================== MEDIA YUKLOVCHI (Havolalar uchun) ====================
@dp.message(
    F.text.regexp(
        r"https?://(?:www\.)?(?:instagram\.com|tiktok\.com|youtube\.com|youtu\.be|fb\.watch)"
    )
)
async def download_media(message: Message):
  url = message.text.strip()
  user_id = message.from_user.id
  name = message.from_user.first_name

  increment_user_requests(user_id)

  processing_msg = await message.answer(
      f"⏳ **{name}**, havola qabul qilindi. Media yuklab olinmoqda va musiqa qidirilmoqda..."
  )

  video_file = f"video_{user_id}.mp4"
  audio_file = f"audio_{user_id}.mp3"

  ydl_opts_video = {
      "format": "best[ext=mp4]/best",
      "outtmpl": f"video_{user_id}.%(ext)s",
      "quiet": True,
  }

  ydl_opts_audio = {
      "format": "bestaudio/best",
      "postprocessors": [{
          "key": "FFmpegExtractAudio",
          "preferredcodec": "mp3",
          "preferredquality": "192",
      }],
      "outtmpl": f"audio_{user_id}",
      "quiet": True,
  }

  try:
    # 1. Videoni yuklab olish
    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
      info = ydl.extract_info(url, download=True)
      filename = ydl.prepare_filename(info)
      if os.path.exists(filename) and filename != video_file:
        os.rename(filename, video_file)

    if os.path.exists(video_file):
      await message.answer_video(
          video=FSInputFile(video_file),
          caption=f"🎬 Mana, {name}! Siz so'ragan video.",
      )

    # 2. Musiqani yuklab olish
    try:
      with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl_audio:
        ydl_audio.extract_info(url, download=True)

      real_audio_path = audio_file + ".mp3"
      if os.path.exists(real_audio_path):
        await message.answer_audio(
            audio=FSInputFile(real_audio_path),
            caption=f"🎵 {name}, videodagi musiqa (Kuy navo)",
        )
    except Exception as audio_err:
      logging.info(f"Audio ajratishda xatolik: {audio_err}")

    await bot.delete_message(
        chat_id=message.chat.id, message_id=processing_msg.message_id
    )

  except Exception as e:
    await message.answer(
        f"❌ Kechirasiz, **{name}**, bu havoladan media yuklab bo'lmadi."
    )
    logging.error(f"Xatolik: {e}")
    await bot.delete_message(
        chat_id=message.chat.id, message_id=processing_msg.message_id
    )

  finally:
    for f in [
        video_file,
        audio_file,
        audio_file + ".mp3",
        f"video_{user_id}.webm",
        f"video_{user_id}.mkv",
    ]:
      if os.path.exists(f):
        try:
          os.remove(f)
        except:
          pass


# ==================== ODDIY MATN YOZGANDA ====================
@dp.message(F.text)
async def handle_other_text(message: Message):
  if message.text.lower() == "sanoq":
    return

  name = message.from_user.first_name
  await message.answer(
      f"Tushunarli, **{name}**! 😊 Iltimos, menga faqat Instagram, YouTube yoki TikTok havolasini yuboring."
  )


async def main():
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
