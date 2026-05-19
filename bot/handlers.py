from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import FONT_FILES, MAX_TEXT_LENGTH
from bot.database import get_user_settings, update_user_setting
from bot.image_gen import text_to_image
from bot.text_audio import get_pinyin_and_translation, get_tts_voice

router = Router()

async def process_text(message: Message, text: str):
    text = text.strip()[:MAX_TEXT_LENGTH]
    if not text:
        return
        
    settings = get_user_settings(message.from_user.id)
    image_file = text_to_image(text, settings["font"], settings["color"], settings["vertical"])
    
    caption = get_pinyin_and_translation(text) if settings["extra_info"] else ""
    await message.reply_photo(photo=image_file, caption=caption, parse_mode="Markdown")
    
    if settings["extra_info"]:
        voice_file = get_tts_voice(text)
        if voice_file:
            await message.answer_voice(voice=voice_file)

def get_settings_keyboard(user_id: int):
    settings = get_user_settings(user_id)
    builder = InlineKeyboardBuilder()
    
    for key, info in FONT_FILES.items():
        btn_text = f"✅ {info['name']}" if key == settings["font"] else info['name']
        builder.button(text=btn_text, callback_data=f"set_font_{key}")
        
    vert_text = "✅ Vertical: ON" if settings["vertical"] else "❌ Vertical: OFF"
    builder.button(text=vert_text, callback_data="toggle_vertical")
    
    info_text = "✅ Audio & Text: ON" if settings["extra_info"] else "❌ Audio & Text: OFF"
    builder.button(text=info_text, callback_data="toggle_info")
    
    builder.adjust(1)
    return builder.as_markup()

@router.message(Command("start", "help"))
async def help_cmd(message: Message):
    help_text = (
        "🐼 **Advanced Chinese Bot**\n\n"
        "**Commands:**\n"
        "👉 `/settings` - Configure font, vertical mode, and extra info\n"
        "👉 `/color red` - Change text color (red, blue, #FF0000, etc.)\n"
        "👉 `/ch <text>` - Generate image in groups\n"
    )
    await message.reply(help_text, parse_mode="Markdown")

@router.message(Command("color"))
async def color_cmd(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Please specify a color! Example: `/color red`")
        return
    new_color = args[1]
    update_user_setting(message.from_user.id, "color", new_color)
    await message.reply(f"Color updated to **{new_color}**!", parse_mode="Markdown")

@router.message(Command("settings", "font"))
async def settings_cmd(message: Message):
    markup = get_settings_keyboard(message.from_user.id)
    await message.reply("⚙️ **Settings**:", reply_markup=markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("set_font_"))
async def set_font(callback: CallbackQuery):
    font_key = callback.data.replace("set_font_", "")
    update_user_setting(callback.from_user.id, "font", font_key)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(callback.from_user.id))

@router.callback_query(F.data.in_(["toggle_vertical", "toggle_info"]))
async def toggle_settings(callback: CallbackQuery):
    key = "vertical" if callback.data == "toggle_vertical" else "extra_info"
    current = get_user_settings(callback.from_user.id)[key]
    update_user_setting(callback.from_user.id, key, not current)
    await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(callback.from_user.id))

@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def private_msg(message: Message):
    await process_text(message, message.text)

@router.message(F.chat.type.in_({"group", "supergroup"}), Command("ch"))
async def group_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    text = args[1] if len(args) > 1 else ""
    if not text and message.reply_to_message and message.reply_to_message.text:
        text = message.reply_to_message.text
    if text:
        await process_text(message, text)

@router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def group_mention(message: Message, bot: Bot):
    bot_info = await bot.get_me()
    mention = f"@{bot_info.username}"
    if mention in message.text:
        text = message.text.replace(mention, "").strip()
        if text:
            await process_text(message, text)
