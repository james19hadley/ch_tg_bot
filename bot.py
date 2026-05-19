import asyncio
import io
import json
import logging
import os
import sys

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, BufferedInputFile, BotCommand, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.getenv("BOT_TOKEN")
FONT_SIZE = 150
MAX_TEXT_LENGTH = 100
DATA_FILE = "data/settings.json"

router = Router()

# Define available fonts
FONT_FILES = {
    "sans_thin": {"path": "fonts/Sans-Thin.otf", "name": "Sans Thin"},
    "sans_light": {"path": "fonts/Sans-Light.otf", "name": "Sans Light"},
    "sans_regular": {"path": "fonts/Sans-Regular.otf", "name": "Sans Regular (Default)"},
    "sans_medium": {"path": "fonts/Sans-Medium.otf", "name": "Sans Medium"},
    "sans_bold": {"path": "fonts/Sans-Bold.otf", "name": "Sans Bold"},
    "sans_black": {"path": "fonts/Sans-Black.otf", "name": "Sans Black (Thickest)"},
    "serif_regular": {"path": "fonts/Serif-Regular.otf", "name": "Serif Regular (Classic)"},
}

DEFAULT_FONT = "sans_regular"

# Load fonts into memory (Zero I/O during image generation)
loaded_fonts = {}
for key, info in FONT_FILES.items():
    try:
        loaded_fonts[key] = ImageFont.truetype(info["path"], FONT_SIZE)
    except IOError:
        logging.error(f"Font {info['path']} not found. Skipping.")

if not loaded_fonts:
    logging.error("No fonts loaded! Exiting.")
    sys.exit(1)

# In-memory user settings
user_settings = {}

def load_settings():
    global user_settings
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)

def save_settings():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_settings, f)

def get_user_font(user_id: int):
    font_key = user_settings.get(str(user_id), DEFAULT_FONT)
    # Fallback if font is missing
    return loaded_fonts.get(font_key, loaded_fonts[DEFAULT_FONT])

def text_to_image(text: str, font) -> BufferedInputFile:
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
        
    user_font = get_user_font(message.from_user.id)
    image_file = text_to_image(text, user_font)
    
    await message.reply_photo(photo=image_file)

# --- Commands ---

@router.message(Command("start", "help"))
async def handle_help(message: Message):
    help_text = (
        "🐼 **Chinese Writing Bot**\n\n"
        "Send me Chinese characters, and I will generate a clear image for you.\n\n"
        "**How to use:**\n"
        "1. In private: Just send any text.\n"
        "2. In groups: Use `/ch <text>` or tag me `@bot_name <text>`.\n"
        "3. Reply to a message with `/ch` to convert it.\n\n"
        "**Commands:**\n"
        "👉 `/font` - Change your preferred font\n"
        "👉 `/help` - Show this message"
    )
    await message.reply(help_text, parse_mode="Markdown")

@router.message(Command("font"))
async def handle_font_command(message: Message):
    builder = InlineKeyboardBuilder()
    current_font = user_settings.get(str(message.from_user.id), DEFAULT_FONT)
    
    for key, info in FONT_FILES.items():
        # Add a checkmark to the currently selected font
        btn_text = f"✅ {info['name']}" if key == current_font else info['name']
        builder.button(text=btn_text, callback_data=f"setfont_{key}")
        
    builder.adjust(1) # 1 button per row
    await message.reply("Select your preferred font:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("setfont_"))
async def handle_font_selection(callback: CallbackQuery):
    font_key = callback.data.replace("setfont_", "")
    user_id = str(callback.from_user.id)
    
    if font_key in FONT_FILES:
        user_settings[user_id] = font_key
        save_settings() # Save to file immediately
        
        font_name = FONT_FILES[font_key]['name']
        await callback.answer(f"Font changed to {font_name}!")
        
        # Edit the message to update the checkmarks
        builder = InlineKeyboardBuilder()
        for key, info in FONT_FILES.items():
            btn_text = f"✅ {info['name']}" if key == font_key else info['name']
            builder.button(text=btn_text, callback_data=f"setfont_{key}")
        builder.adjust(1)
        
        await callback.message.edit_text("Select your preferred font:", reply_markup=builder.as_markup())
    else:
        await callback.answer("Error changing font.")

# --- Message Handlers ---

@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
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

# --- Startup ---

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="ch", description="Generate image from Chinese text"),
        BotCommand(command="font", description="Change font style"),
        BotCommand(command="help", description="Show help and instructions"),
    ]
    await bot.set_my_commands(commands)

async def main():
    logging.basicConfig(level=logging.INFO)
    
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set!")
        return

    load_settings()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await setup_bot_commands(bot)
    
    logging.info("Bot is starting...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())