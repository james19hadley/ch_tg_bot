import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta

from aiogram import Bot

from bot.database import get_all_push_targets, update_last_push
from bot.vocabulary import get_random_word, count_words
from bot.image_gen import text_to_image
from bot.text_audio import get_extra_info, get_tts_voice
from bot.database import get_user_settings

logger = logging.getLogger(__name__)

# Pushes are only sent between these hours (server local time)
PUSH_HOUR_START = 9
PUSH_HOUR_END = 22

# How often the scheduler loop wakes up to check (minutes)
CHECK_INTERVAL_MINUTES = 20


def _should_push_now(last_push_at_str: str | None, pushes_per_day: int) -> bool:
    """Decide if it's time for another push based on last push time and daily quota."""
    now = datetime.now()

    # Respect quiet hours
    if not (PUSH_HOUR_START <= now.hour < PUSH_HOUR_END):
        return False

    if last_push_at_str is None:
        # Never pushed — fire with 70% probability to spread out cold-starts
        return random.random() < 0.7

    try:
        last = datetime.fromisoformat(last_push_at_str)
    except (ValueError, TypeError):
        return True

    # Minimum gap between pushes = available hours divided by pushes per day, with jitter
    available_hours = PUSH_HOUR_END - PUSH_HOUR_START
    base_gap_hours = available_hours / max(pushes_per_day, 1)
    # Add random jitter of ±30% so it feels natural
    jitter = random.uniform(-0.3, 0.3) * base_gap_hours
    gap = timedelta(hours=base_gap_hours + jitter)

    return (datetime.now() - last) >= gap


async def _send_push(bot: Bot, user_id: int, chat_id: int) -> bool:
    """Send a random vocabulary word to the user. Returns True on success."""
    if count_words(user_id) == 0:
        return False

    word = get_random_word(user_id)
    if not word:
        return False

    text = word["text"]
    settings = get_user_settings(user_id)

    try:
        image_file = text_to_image(text, settings["font"], settings["color"], settings["vertical"])
        caption = get_extra_info(text, settings["pinyin"], settings["ru"], settings["en"])
        if caption:
            caption = f"📚 *Из твоего словаря*\n\n{caption}"
        else:
            caption = "📚 *Из твоего словаря*"

        await bot.send_photo(chat_id=chat_id, photo=image_file, caption=caption, parse_mode="Markdown")

        if settings["audio"]:
            voice_file = await get_tts_voice(text)
            if voice_file:
                await bot.send_voice(chat_id=chat_id, voice=voice_file)

        update_last_push(user_id)
        return True

    except Exception as e:
        logger.warning(f"Push failed for user {user_id}: {e}")
        return False


async def scheduler_loop(bot: Bot):
    """Background task that runs forever, sending pushes at random intervals."""
    logger.info("Push scheduler started.")
    while True:
        try:
            targets = get_all_push_targets()
            for target in targets:
                if _should_push_now(target["last_push_at"], target["pushes_per_day"]):
                    await _send_push(bot, target["user_id"], target["chat_id"])
                    # Small delay between users to avoid burst
                    await asyncio.sleep(random.uniform(1, 5))
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")

        # Sleep until next check, with a small random jitter
        sleep_minutes = CHECK_INTERVAL_MINUTES + random.uniform(-5, 5)
        await asyncio.sleep(sleep_minutes * 60)
