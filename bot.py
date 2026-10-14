import os
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
import yt_dlp

TOKEN = "8617585421:AAGGXyKGNI7q83sjPugW0kqtqZ0x--P-aAQ"
ADMIN_ID = 1440318650  # Raqam ko'rinishida yozing

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

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
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
  user_id = message.from_user.id
  name = message.from_user.first_name

  cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
  result = cursor.fetchone()

  if not result:
    cursor.execute(
        "INSERT INTO users (user_id, request_count) VALUES (?, 0)", (user_id,)
    )
    conn.commit()

  await message.reply(
      f"Assalomu alaykum, **{name}**! 👋\n\n"
      "Menga Instagram, YouTube yoki TikTok havolasini yuboring.\n"
      "Men sizga videoni hamda undagi musiqani topib beraman!",
      parse_mode="Markdown",
  )


# ==================== SANOQ (Faqat Admin uchun) ====================
@dp.message_handler(lambda message: message.text and message.text.lower() == "sanoq")
async def show_sanoq(message: types.Message):
  if message.from_user.id == ADMIN_ID:
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(request_count) FROM users")
    total_requests = cursor.fetchone()[0] or 0

    await message.reply(
        f"📊 **BOT SANOQLARI:**\n\n"
        f"👤 Jami foydalanuvchilar: **{count} ta**\n"
        f"📥 Jami yuklab olingan medialar: **{total_requests} marta**",
        parse_mode="Markdown",
    )


# ==================== MEDIA VA MUSIQA YUKLOVCHI ====================
@dp.message_handler(
    lambda message: message.text
    and any(
        x in message.text
        for x in ["instagram.com", "tiktok.com", "youtube.com", "youtu.be"]
    )
)
async def download_media(message: types.Message):
  url = message.text.strip()
  user_id = message.from_user.id
  name = message.from_user.first_name

  increment_user_requests(user_id)

  processing_msg = await message.reply(
      f"⏳ **{name}**, havola qabul qilindi. Media va musiqa yuklab olinmoqda...",
      parse_mode="Markdown",
  )

  video_file = f"video_{user_id}.mp4"
  audio_file = f"audio_{user_id}.mp3"

  ydl_opts_video = {
      "format": "best[ext=mp4]/best",
      "outtmpl": f"video_{user_id}.%(ext)s",
      "quiet": True,
      "no_warnings": True,
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
      "no_warnings": True,
  }

  try:
    # 1. Videoni yuklab olish
    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
      info = ydl.extract_info(url, download=True)
      filename = ydl.prepare_filename(info)
      if os.path.exists(filename) and filename != video_file:
        os.rename(filename, video_file)

    if os.path.exists(video_file):
      await message.reply_video(
          video=open(video_file, "rb"),
          caption=f"🎬 Mana, {name}! Siz so'ragan video.",
      )

    # 2. Musiqani yuklab olish
    try:
      with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl_audio:
        ydl_audio.extract_info(url, download=True)

      real_audio_path = audio_file + ".mp3"
      if os.path.exists(real_audio_path):
        await message.reply_audio(
            audio=open(real_audio_path, "rb"),
            caption=f"🎵 {name}, videodagi musiqa (Kuy navo)",
        )
    except Exception as audio_err:
      print(f"Musiqa topishda xatolik: {audio_err}")

    await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)

  except Exception as e:
    await message.reply(
        f"❌ Kechirasiz, **{name}**, bu havoladan media yuklab bo'lmadi.",
        parse_mode="Markdown",
    )
    print(f"Xatolik: {e}")
    await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)

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


if __name__ == "__main__":
  executor.start_polling(dp, skip_updates=True)
