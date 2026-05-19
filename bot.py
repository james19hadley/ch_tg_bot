import asyncio
import io
import logging
import os
import sys

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.getenv("BOT_TOKEN")
FONT_PATH = "font.ttf"
FONT_SIZE = 150
MAX_TEXT_LENGTH = 100

router = Router()

try:
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
except IOError:
    logging.error(f"Font {FONT_PATH} not found!")
    sys.exit(1)

def text_to_image(text: str) -> BufferedInputFile:
    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    padding = 40
    width = text_width + padding * 2
    height = text_height + padding * 2
    
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    
    draw.multiline_text((padding - bbox[0], padding - bbox[1]), text, font=font, fill="black")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return BufferedInputFile(buffer.getvalue(), filename="chinese.png")

async def send_image(message: Message, text: str):
    text = text.strip()[:MAX_TEXT_LENGTH]
    if not text:
        return
        
    image_file = text_to_image(text)
    await message.reply_photo(photo=image_file)

@router.message(F.chat.type == "private", F.text)
async def handle_private_message(message: Message):
    await send_image(message, message.text)

@router.message(F.chat.type.in_({"group", "supergroup"}), Command("ch"))
async def handle_group_command(message: Message):
    args = message.text.split(maxsplit=1)
    text = args[1] if len(args) > 1 else ""
    
    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
        
    if text:
        await send_image(message, text)

@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def handle_group_mention(message: Message, bot: Bot):
    bot_info = await bot.get_me()
    mention = f"@{bot_info.username}"
    
    if mention in message.text:
        text = message.text.replace(mention, "").strip()
        if text:
            await send_image(message, text)

async def main():
    logging.basicConfig(level=logging.INFO)
    
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set!")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    logging.info("Bot is starting...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())