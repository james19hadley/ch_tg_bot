from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import FONT_FILES, MAX_TEXT_LENGTH
from bot.database import get_user_settings, update_user_setting
from bot.image_gen import text_to_image
from bot.text_audio import get_extra_info, get_tts_voice, translate_to_chinese
from bot.commands import get_help_text
from bot.utils import has_chinese

router = Router()

async def process_text(message: Message, text: str):
    text = text.strip()[:MAX_TEXT_LENGTH]
    if not text:
        return
        
    is_auto_translated = False
    if not has_chinese(text):
        # Auto-translate to Chinese if no Chinese characters detected!
        text = translate_to_chinese(text)
        is_auto_translated = True
        
    settings = get_user_settings(message.from_user.id)
    image_file = text_to_image(text, settings["font"], settings["color"], settings["vertical"])
    
    caption = get_extra_info(text, settings["pinyin"], settings["ru"], settings["en"])
    if is_auto_translated:
        caption = f"🔄 *Auto-translated to Chinese:*\n\n{caption}"
        
    await message.reply_photo(photo=image_file, caption=caption, parse_mode="Markdown")
    
    if settings["audio"]:
        voice_file = await get_tts_voice(text)
        if voice_file:
            await message.answer_voice(voice=voice_file)

def get_main_settings_keyboard(user_id: int):
    s = get_user_settings(user_id)
    b = InlineKeyboardBuilder()
    
    # Toggles
    b.button(text=f"{'✅' if s['vertical'] else '❌'} Vertical Mode", callback_data="toggle_vertical")
    b.button(text=f"{'✅' if s['pinyin'] else '❌'} Pinyin", callback_data="toggle_pinyin")
    b.button(text=f"{'✅' if s['audio'] else '❌'} Audio (TTS)", callback_data="toggle_audio")
    b.button(text=f"{'✅' if s['ru'] else '❌'} RU Translation", callback_data="toggle_ru")
    b.button(text=f"{'✅' if s['en'] else '❌'} EN Translation", callback_data="toggle_en")
    
    # Sub-menu button
    b.button(text="🔠 Change Font ➡️", callback_data="menu_fonts")
    
    b.adjust(1)
    return b.as_markup()

def get_fonts_keyboard(user_id: int):
    s = get_user_settings(user_id)
    b = InlineKeyboardBuilder()
    
    for key, info in FONT_FILES.items():
        btn_text = f"✅ {info['name']}" if key == s["font"] else info['name']
        b.button(text=btn_text, callback_data=f"set_font_{key}")
        
    b.button(text="⬅️ Back to Settings", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()

@router.message(Command("start", "help"))
async def help_cmd(message: Message):
    await message.reply(get_help_text(), parse_mode="Markdown")

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
    await message.reply("⚙️ **Main Settings**:", reply_markup=get_main_settings_keyboard(message.from_user.id), parse_mode="Markdown")

# --- Callbacks for Navigation ---
@router.callback_query(F.data == "menu_fonts")
async def nav_fonts(callback: CallbackQuery):
    await callback.message.edit_text("🔠 **Select Font**:", reply_markup=get_fonts_keyboard(callback.from_user.id), parse_mode="Markdown")

@router.callback_query(F.data == "menu_main")
async def nav_main(callback: CallbackQuery):
    await callback.message.edit_text("⚙️ **Main Settings**:", reply_markup=get_main_settings_keyboard(callback.from_user.id), parse_mode="Markdown")

# --- Callbacks for Actions ---
@router.callback_query(F.data.startswith("set_font_"))
async def set_font(callback: CallbackQuery):
    font_key = callback.data.replace("set_font_", "")
    update_user_setting(callback.from_user.id, "font", font_key)
    await callback.message.edit_reply_markup(reply_markup=get_fonts_keyboard(callback.from_user.id))

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: CallbackQuery):
    key = callback.data.replace("toggle_", "")
    current = get_user_settings(callback.from_user.id)[key]
    update_user_setting(callback.from_user.id, key, not current)
    await callback.message.edit_reply_markup(reply_markup=get_main_settings_keyboard(callback.from_user.id))

# --- Message Handlers ---
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
