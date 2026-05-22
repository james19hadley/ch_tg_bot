from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import FONT_FILES, MAX_TEXT_LENGTH
from bot.database import (
    get_user_settings, update_user_setting,
    get_push_settings, upsert_push_settings,
)
from bot.vocabulary import add_word, get_words, delete_word, count_words, word_exists
from bot.image_gen import text_to_image
from bot.text_audio import get_extra_info, get_tts_voice, translate_to_chinese
from bot.commands import get_help_text
from bot.utils import has_chinese

router = Router()

# ── Color palette ──────────────────────────────────────────────────────────────

COLOR_OPTIONS = {
    "black":   ("⚫", "Black"),
    "crimson": ("🔴", "Crimson"),
    "navy":    ("🔵", "Navy Blue"),
    "sepia":   ("🟤", "Sepia"),
    "forest":  ("🟢", "Forest"),
    "purple":  ("🟣", "Purple"),
}

COLOR_VALUES = {
    "black":   "black",
    "crimson": "#c0392b",
    "navy":    "#1a3a6b",
    "sepia":   "#7b4f2e",
    "forest":  "#1e7a45",
    "purple":  "#6c3483",
}

# ── Core processing ────────────────────────────────────────────────────────────

async def process_text(message: Message, text: str):
    text = text.strip()[:MAX_TEXT_LENGTH]
    if not text:
        return

    is_auto_translated = False
    if not has_chinese(text):
        text = translate_to_chinese(text)
        is_auto_translated = True

    settings = get_user_settings(message.from_user.id)
    color = COLOR_VALUES.get(settings["color"], settings["color"])
    image_file = text_to_image(text, settings["font"], color, settings["vertical"])

    caption = get_extra_info(text, settings["pinyin"], settings["ru"], settings["en"])
    if is_auto_translated:
        caption = f"🔄 *Auto-translated to Chinese:*\n\n{caption}"

    b = InlineKeyboardBuilder()
    if word_exists(message.from_user.id, text):
        b.button(text="✅ In vocab", callback_data="vocab_already")
    else:
        b.button(text="💾 Save to vocab", callback_data=f"vocab_save_{text[:50]}")

    await message.reply_photo(
        photo=image_file,
        caption=caption or None,
        parse_mode="Markdown",
        reply_markup=b.as_markup(),
    )

    if settings["audio"]:
        voice_file = await get_tts_voice(text)
        if voice_file:
            await message.answer_voice(voice=voice_file)

# ── Keyboards ──────────────────────────────────────────────────────────────────

def get_main_settings_keyboard(user_id: int):
    s = get_user_settings(user_id)
    push = get_push_settings(user_id)
    push_count = push["pushes_per_day"] if push and push["enabled"] else 0

    b = InlineKeyboardBuilder()
    b.button(text=f"{'✅' if s['vertical'] else '❌'} Vertical Mode",  callback_data="toggle_vertical")
    b.button(text=f"{'✅' if s['pinyin']   else '❌'} Pinyin",          callback_data="toggle_pinyin")
    b.button(text=f"{'✅' if s['audio']    else '❌'} Audio (TTS)",     callback_data="toggle_audio")
    b.button(text=f"{'✅' if s['ru']       else '❌'} RU Translation",  callback_data="toggle_ru")
    b.button(text=f"{'✅' if s['en']       else '❌'} EN Translation",  callback_data="toggle_en")
    b.button(text="🔠 Change Font ➡️",                                   callback_data="menu_fonts")
    b.button(text="🎨 Change Color ➡️",                                  callback_data="menu_color")

    push_label = f"📬 Daily Pushes: {push_count}/day" if push_count > 0 else "📬 Daily Pushes: off"
    b.button(text=push_label, callback_data="menu_push")
    b.adjust(1)
    return b.as_markup()

def get_fonts_keyboard(user_id: int):
    s = get_user_settings(user_id)
    b = InlineKeyboardBuilder()
    for key, info in FONT_FILES.items():
        label = f"✅ {info['name']}" if key == s["font"] else info["name"]
        b.button(text=label, callback_data=f"set_font_{key}")
    b.button(text="⬅️ Back", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()

def get_color_keyboard(user_id: int):
    s = get_user_settings(user_id)
    b = InlineKeyboardBuilder()
    for key, (emoji, name) in COLOR_OPTIONS.items():
        label = f"✅ {emoji} {name}" if key == s["color"] else f"{emoji} {name}"
        b.button(text=label, callback_data=f"set_color_{key}")
    b.button(text="⬅️ Back", callback_data="menu_main")
    b.adjust(1)
    return b.as_markup()

def get_push_keyboard(user_id: int):
    push = get_push_settings(user_id)
    current = push["pushes_per_day"] if push and push["enabled"] else 0
    b = InlineKeyboardBuilder()
    for val, label in [(0, "Off"), (1, "1/day"), (2, "2/day"), (3, "3/day"), (5, "5/day")]:
        mark = "✅ " if val == current else ""
        b.button(text=f"{mark}{label}", callback_data=f"set_push_{val}")
    b.button(text="⬅️ Back", callback_data="menu_main")
    b.adjust(2)
    return b.as_markup()

# ── Vocabulary keyboard ────────────────────────────────────────────────────────

VOCAB_PAGE_SIZE = 8

def get_vocab_keyboard(user_id: int, page: int = 0, delete_mode: bool = False):
    words = get_words(user_id, limit=VOCAB_PAGE_SIZE, offset=page * VOCAB_PAGE_SIZE)
    total = count_words(user_id)
    total_pages = max(1, (total + VOCAB_PAGE_SIZE - 1) // VOCAB_PAGE_SIZE)

    b = InlineKeyboardBuilder()
    for w in words:
        if delete_mode:
            b.button(text=f"❌ {w['text']}", callback_data=f"vdel_{w['id']}_{page}")
        else:
            b.button(text=w["text"], callback_data="vocab_noop")
    b.adjust(2)

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️", callback_data=f"vpage_{page-1}_{int(delete_mode)}")
    nav.button(text=f"{page+1}/{total_pages}", callback_data="vocab_noop")
    if (page + 1) < total_pages:
        nav.button(text="➡️", callback_data=f"vpage_{page+1}_{int(delete_mode)}")
    b.attach(nav)

    action = InlineKeyboardBuilder()
    if delete_mode:
        action.button(text="✅ Done", callback_data=f"vpage_{page}_0")
    else:
        action.button(text="🗑 Delete mode", callback_data=f"vpage_{page}_1")
    b.attach(action)

    return b.as_markup(), words, total

# ── Commands ───────────────────────────────────────────────────────────────────

@router.message(Command("start", "help"))
async def help_cmd(message: Message):
    await message.reply(get_help_text(), parse_mode="Markdown")

@router.message(Command("settings"))
async def settings_cmd(message: Message):
    await message.reply(
        "⚙️ **Settings:**",
        reply_markup=get_main_settings_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )

@router.message(Command("vocab"))
async def vocab_cmd(message: Message):
    total = count_words(message.from_user.id)
    if total == 0:
        await message.reply(
            "📭 Your vocabulary is empty.\n\n"
            "Send any Chinese text and tap **💾 Save to vocab**, "
            "or use `/save <word>` in a group.",
            parse_mode="Markdown",
        )
        return
    markup, words, total = get_vocab_keyboard(message.from_user.id, page=0)
    await message.reply(
        f"📚 **Your vocabulary** ({total} words):",
        reply_markup=markup,
        parse_mode="Markdown",
    )

@router.message(Command("save"))
async def save_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    text = ""

    if len(args) > 1:
        text = args[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        candidate = message.reply_to_message.text.strip()
        if has_chinese(candidate):
            text = candidate[:MAX_TEXT_LENGTH]

    if not text or not has_chinese(text):
        await message.reply(
            "⚠️ Please provide Chinese text: `/save 你好` or reply to a message.",
            parse_mode="Markdown",
        )
        return

    pinyin_info = get_extra_info(text, show_pinyin=True, show_ru=True, show_en=True)
    py = ru = en = None
    for line in pinyin_info.split("\n"):
        if "Pinyin" in line:
            py = line.split(":", 1)[-1].strip()
        elif "RU" in line:
            ru = line.split(":", 1)[-1].strip()
        elif "EN" in line:
            en = line.split(":", 1)[-1].strip()

    added = add_word(message.from_user.id, text, pinyin=py, trans_ru=ru, trans_en=en)
    if added:
        await message.reply(f"✅ **{text}** saved to your vocabulary!", parse_mode="Markdown")
    else:
        await message.reply(f"📌 **{text}** is already in your vocabulary.", parse_mode="Markdown")

# ── Callbacks: navigation ──────────────────────────────────────────────────────

@router.callback_query(F.data == "menu_main")
async def nav_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ **Settings:**",
        reply_markup=get_main_settings_keyboard(callback.from_user.id),
        parse_mode="Markdown",
    )

@router.callback_query(F.data == "menu_fonts")
async def nav_fonts(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔠 **Select Font:**",
        reply_markup=get_fonts_keyboard(callback.from_user.id),
        parse_mode="Markdown",
    )

@router.callback_query(F.data == "menu_color")
async def nav_color(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎨 **Select Color:**",
        reply_markup=get_color_keyboard(callback.from_user.id),
        parse_mode="Markdown",
    )

@router.callback_query(F.data == "menu_push")
async def nav_push(callback: CallbackQuery):
    await callback.message.edit_text(
        "📬 **Daily Pushes**\n\n"
        "How many words from your vocab should I send per day?\n"
        "_(Sent at random times between 9:00–22:00)_",
        reply_markup=get_push_keyboard(callback.from_user.id),
        parse_mode="Markdown",
    )

# ── Callbacks: set values ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_font_"))
async def set_font(callback: CallbackQuery):
    font_key = callback.data.replace("set_font_", "")
    update_user_setting(callback.from_user.id, "font", font_key)
    await callback.message.edit_reply_markup(reply_markup=get_fonts_keyboard(callback.from_user.id))
    await callback.answer()

@router.callback_query(F.data.startswith("set_color_"))
async def set_color(callback: CallbackQuery):
    color_key = callback.data.replace("set_color_", "")
    update_user_setting(callback.from_user.id, "color", color_key)
    await callback.message.edit_reply_markup(reply_markup=get_color_keyboard(callback.from_user.id))
    await callback.answer()

@router.callback_query(F.data.startswith("set_push_"))
async def set_push(callback: CallbackQuery):
    count = int(callback.data.replace("set_push_", ""))
    enabled = count > 0
    upsert_push_settings(
        user_id=callback.from_user.id,
        chat_id=callback.message.chat.id,
        enabled=enabled,
        pushes_per_day=count,
    )
    answer = f"✅ Pushes set to {count}/day" if enabled else "🔕 Pushes disabled"
    await callback.message.edit_reply_markup(reply_markup=get_push_keyboard(callback.from_user.id))
    await callback.answer(answer)

@router.callback_query(F.data.startswith("toggle_"))
async def toggle_settings(callback: CallbackQuery):
    key = callback.data.replace("toggle_", "")
    current = get_user_settings(callback.from_user.id)[key]
    update_user_setting(callback.from_user.id, key, not current)
    await callback.message.edit_reply_markup(reply_markup=get_main_settings_keyboard(callback.from_user.id))
    await callback.answer()

# ── Callbacks: vocabulary inline save ─────────────────────────────────────────

@router.callback_query(F.data.startswith("vocab_save_"))
async def vocab_save_inline(callback: CallbackQuery):
    text = callback.data.replace("vocab_save_", "")
    pinyin_info = get_extra_info(text, show_pinyin=True, show_ru=True, show_en=True)
    py = ru = en = None
    for line in pinyin_info.split("\n"):
        if "Pinyin" in line:
            py = line.split(":", 1)[-1].strip()
        elif "RU" in line:
            ru = line.split(":", 1)[-1].strip()
        elif "EN" in line:
            en = line.split(":", 1)[-1].strip()
    added = add_word(callback.from_user.id, text, pinyin=py, trans_ru=ru, trans_en=en)
    if added:
        await callback.answer(f"✅ {text} saved!")
        b = InlineKeyboardBuilder()
        b.button(text="✅ In vocab", callback_data="vocab_already")
        await callback.message.edit_reply_markup(reply_markup=b.as_markup())
    else:
        await callback.answer("📌 Already in vocab")

@router.callback_query(F.data == "vocab_already")
async def vocab_already(callback: CallbackQuery):
    await callback.answer("Already in your vocabulary")

@router.callback_query(F.data == "vocab_noop")
async def vocab_noop(callback: CallbackQuery):
    await callback.answer()

# ── Callbacks: vocabulary pagination & delete ──────────────────────────────────

@router.callback_query(F.data.startswith("vpage_"))
async def vocab_page(callback: CallbackQuery):
    _, page_str, mode_str = callback.data.split("_")
    page = int(page_str)
    delete_mode = bool(int(mode_str))
    total = count_words(callback.from_user.id)
    markup, words, total = get_vocab_keyboard(callback.from_user.id, page, delete_mode)
    header = "🗑 *Tap a word to delete it:*" if delete_mode else f"📚 *Your vocabulary* ({total} words):"
    await callback.message.edit_text(header, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("vdel_"))
async def vocab_delete(callback: CallbackQuery):
    parts = callback.data.split("_")
    word_id = int(parts[1])
    page = int(parts[2])
    deleted = delete_word(callback.from_user.id, word_id)
    await callback.answer("❌ Deleted" if deleted else "Not found")
    total = count_words(callback.from_user.id)
    max_page = max(0, (total + VOCAB_PAGE_SIZE - 1) // VOCAB_PAGE_SIZE - 1)
    page = min(page, max_page)
    markup, _, total = get_vocab_keyboard(callback.from_user.id, page, delete_mode=True)
    await callback.message.edit_text(
        "🗑 *Tap a word to delete it:*",
        reply_markup=markup,
        parse_mode="Markdown",
    )

# ── Message handlers ───────────────────────────────────────────────────────────

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
