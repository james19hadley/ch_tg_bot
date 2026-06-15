from aiogram import Router, F, Bot, BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Callable, Dict, Any, Awaitable

from ch_tg_bot.config import FONT_FILES, MAX_TEXT_LENGTH
import json
from ch_tg_bot.database import (
    get_user_settings, update_user_setting,
    get_push_settings, upsert_push_settings,
    get_all_user_progress,
    upsert_user, set_share_progress,
    get_user_by_username, get_user_by_id,
    add_pairing, remove_pairing, is_paired,
    get_paired_students, get_student_progress,
    upsert_progress_push_config, remove_progress_push_config,
    get_progress_push_config,
)
from ch_tg_bot.vocabulary import add_word, get_words, delete_word, count_words, word_exists
from ch_tg_bot.image_gen import text_to_image
from ch_tg_bot.text_audio import get_extra_info, get_tts_voice, translate_to_chinese
from ch_tg_bot.commands import get_help_text
from ch_tg_bot.utils import has_chinese

class UserUpsertMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user:
            upsert_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
        return await handler(event, data)

router = Router()
router.message.outer_middleware(UserUpsertMiddleware())
router.callback_query.outer_middleware(UserUpsertMiddleware())

# Short-lived in-memory cache: (user_id, msg_id) -> text
# Used to avoid putting long Chinese text in callback_data (64-byte limit)
_save_cache: dict[tuple[int, int], str] = {}

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
    already_saved = word_exists(message.from_user.id, text)
    if already_saved:
        b.button(text="✅ In vocab", callback_data="vocab_already")
    else:
        # Store text in cache keyed by original message id; callback carries only the id
        cache_key = (message.from_user.id, message.message_id)
        _save_cache[cache_key] = text
        b.button(text="💾 Save to vocab", callback_data=f"vs_{message.message_id}")

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

@router.message(Command("id"))
async def id_cmd(message: Message):
    await message.reply(
        f"🔑 *Your Telegram User ID:* `{message.from_user.id}`\n\n"
        f"Copy this ID and paste it into the Hànyīn web app Sync settings to synchronize your progress.",
        parse_mode="Markdown"
    )

def format_progress_report(p: dict) -> str:
    name = p.get('first_name') or p.get('username') or f"User {p['user_id']}"
    username_suffix = f" (@{p['username']})" if p.get('username') else ""
    
    try:
        lessons = json.loads(p.get('lessons_completed', '[]'))
    except Exception:
        lessons = []
    lessons_str = ", ".join(f"Lesson {l}" for l in lessons) if lessons else "None"

    streak = p.get('streak') if p.get('streak') is not None else 0
    score = p.get('score') if p.get('score') is not None else 0
    accuracy = p.get('accuracy') if p.get('accuracy') is not None else 0
    updated_at = p.get('updated_at') or "Never synced"

    return (
        f"👤 *{name}*{username_suffix}\n"
        f"🔥 Streak: *{streak}* days\n"
        f"🏆 Total Score: *{score}* points\n"
        f"📚 Completed: *{lessons_str}*\n"
        f"🎯 Tone Accuracy: *{accuracy}%*\n"
        f"🕒 Last Active: {updated_at}"
    )

@router.message(Command("progress"))
async def progress_cmd(message: Message):
    args = message.text.split()

    # 1. Query for a specific user
    if len(args) > 1:
        target_str = args[1].strip()
        target_user = None

        # Check if target_str is a numeric user_id
        if target_str.isdigit():
            target_user = get_user_by_id(int(target_str))
        else:
            target_user = get_user_by_username(target_str)

        if not target_user:
            await message.reply(
                f"❌ User *{target_str}* not found. "
                f"They must interact with the bot at least once.",
                parse_mode="Markdown"
            )
            return

        target_id = target_user["user_id"]
        # Check permission
        if target_id != message.from_user.id and not target_user.get("share_progress"):
            await message.reply(
                f"🔒 *Access Denied.*\n\n"
                f"User *{target_str}* has disabled progress sharing. "
                f"They need to run `/share on` in the bot to allow sharing.",
                parse_mode="Markdown"
            )
            return

        progress = get_student_progress(target_id)
        if not progress or (progress.get("streak") is None and progress.get("score") is None):
            await message.reply(f"👤 *{target_str}* has not synchronized any study progress yet.", parse_mode="Markdown")
            return

        await message.reply(f"🎓 *Progress Report:*\n\n{format_progress_report(progress)}", parse_mode="Markdown")
        return

    # 2. Query for self and paired students
    own_progress = get_student_progress(message.from_user.id)
    paired_students = get_paired_students(message.from_user.id)

    sections = []

    # Own Progress section
    if own_progress and (own_progress.get("streak") is not None or own_progress.get("score") is not None):
        sections.append(f"⭐️ *Your Progress:*\n{format_progress_report(own_progress)}")
    else:
        sections.append(
            "⭐️ *Your Progress:*\n"
            "You haven't synchronized your progress yet. "
            "Go to the Hànyīn web app, open Sync settings, enter your user ID, and sync!"
        )

    # Paired Students section
    if paired_students:
        paired_sections = ["👥 *Tracked Students:*"]
        for student in paired_students:
            # Check if student allows sharing
            if not student.get("share_progress"):
                name = student.get("first_name") or student.get("username") or f"Student {student['user_id']}"
                username_suffix = f" (@{student['username']})" if student.get('username') else ""
                paired_sections.append(f"👤 *{name}*{username_suffix}\n🔒 _Sharing disabled_")
            else:
                paired_sections.append(format_progress_report(student))
        sections.append("\n\n".join(paired_sections))
    else:
        sections.append(
            "💡 *Tip:* You are not tracking anyone. "
            "Use `/track @username` to automatically follow your students' progress."
        )

    await message.reply("\n\n".join(sections), parse_mode="Markdown")

@router.message(Command("share"))
async def share_cmd(message: Message):
    args = message.text.split()
    if len(args) < 2 or args[1].lower() not in ("on", "off"):
        # Show current sharing status
        student = get_student_progress(message.from_user.id)
        sharing = "ON" if (student and student.get("share_progress")) else "OFF"
        await message.reply(
            f"🔒 *Progress Sharing status:* `{sharing}`\n\n"
            f"To change it, use:\n"
            f"👉 `/share on` — enable sharing (so Maria/teachers can track you)\n"
            f"👉 `/share off` — disable sharing",
            parse_mode="Markdown"
        )
        return

    val = args[1].lower() == "on"
    set_share_progress(message.from_user.id, val)
    status_str = "enabled" if val else "disabled"
    await message.reply(f"✅ Progress sharing has been *{status_str}*.", parse_mode="Markdown")

@router.message(Command("track"))
async def track_cmd(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("⚠️ Please specify the username to track: `/track @username`", parse_mode="Markdown")
        return

    target_username = args[1].strip()
    student = get_user_by_username(target_username)
    if not student:
        await message.reply(
            f"❌ User *{target_username}* not found. "
            f"They must launch the bot first so their username is registered.",
            parse_mode="Markdown"
        )
        return

    if not student.get("share_progress"):
        await message.reply(
            f"❌ User *{target_username}* has progress sharing turned off. "
            f"They need to run `/share on` in the bot before you can track them.",
            parse_mode="Markdown"
        )
        return

    add_pairing(message.from_user.id, student["user_id"])
    name = student["first_name"] or student["username"] or f"Student {student['user_id']}"
    await message.reply(f"✅ You are now tracking progress for *{name}* ({target_username}).", parse_mode="Markdown")

@router.message(Command("untrack"))
async def untrack_cmd(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("⚠️ Please specify the username to stop tracking: `/untrack @username`", parse_mode="Markdown")
        return

    target_username = args[1].strip()
    student = get_user_by_username(target_username)
    if not student:
        await message.reply(f"❌ User *{target_username}* not found.", parse_mode="Markdown")
        return

    removed = remove_pairing(message.from_user.id, student["user_id"])
    if removed:
        name = student["first_name"] or student["username"] or f"Student {student['user_id']}"
        await message.reply(f"✅ Stopped tracking progress for *{name}* ({target_username}).", parse_mode="Markdown")
    else:
        await message.reply(f"📌 You are not tracking *{target_username}*.", parse_mode="Markdown")

@router.message(Command("set_spam_topic"))
async def set_spam_topic_cmd(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("⚠️ This command can only be used in group chats or forum topics.", parse_mode="Markdown")
        return

    args = message.text.split()
    target_user = None
    if len(args) > 1:
        target_username = args[1].strip()
        target_user = get_user_by_username(target_username)
        if not target_user:
            await message.reply(f"❌ User *{target_username}* not found.", parse_mode="Markdown")
            return
    else:
        target_user = get_user_by_id(message.from_user.id)

    target_id = target_user["user_id"]
    target_username = target_user["username"] or f"user_{target_id}"

    # Check permissions
    if target_id != message.from_user.id:
        if not is_paired(message.from_user.id, target_id):
            await message.reply(
                f"❌ You must be tracking *@{target_username}* using `/track @{target_username}` "
                f"first before you can configure their spam topic.",
                parse_mode="Markdown"
            )
            return

    thread_id = message.message_thread_id
    upsert_progress_push_config(target_id, message.chat.id, thread_id)

    topic_name = "this topic" if thread_id else "this chat"
    await message.reply(
        f"🔔 *Progress Updates Configured!*\n\n"
        f"Study updates for *@{target_username}* will now be pushed to {topic_name}.",
        parse_mode="Markdown"
    )

@router.message(Command("unset_spam_topic"))
async def unset_spam_topic_cmd(message: Message):
    args = message.text.split()
    target_user = None
    if len(args) > 1:
        target_username = args[1].strip()
        target_user = get_user_by_username(target_username)
        if not target_user:
            await message.reply(f"❌ User *{target_username}* not found.", parse_mode="Markdown")
            return
    else:
        target_user = get_user_by_id(message.from_user.id)

    target_id = target_user["user_id"]
    target_username = target_user["username"] or f"user_{target_id}"

    removed = remove_progress_push_config(target_id)
    if removed:
        await message.reply(f"🔕 Stopped routing progress updates for *@{target_username}*.", parse_mode="Markdown")
    else:
        await message.reply(f"📌 No active spam topic configuration found for *@{target_username}*.", parse_mode="Markdown")

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

@router.callback_query(F.data.startswith("vs_"))
async def vocab_save_inline(callback: CallbackQuery):
    try:
        orig_msg_id = int(callback.data.replace("vs_", ""))
    except ValueError:
        await callback.answer("Error: invalid key")
        return

    cache_key = (callback.from_user.id, orig_msg_id)
    text = _save_cache.get(cache_key)
    if not text:
        await callback.answer("⚠️ Couldn't find the word (bot may have restarted)")
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

    added = add_word(callback.from_user.id, text, pinyin=py, trans_ru=ru, trans_en=en)
    if added:
        _save_cache.pop(cache_key, None)  # clean up
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
