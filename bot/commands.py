from aiogram.types import BotCommand

# Единый список команд для бота и для /help
BOT_COMMANDS = [
    BotCommand(command="settings", description="Open settings (Fonts, Vertical, Audio)"),
    BotCommand(command="color", description="Change text color (e.g., /color red)"),
    BotCommand(command="ch", description="Generate image in groups"),
    BotCommand(command="help", description="Show this help message"),
]

# Общее описание фичей бота
FEATURES_TEXT = (
    "🐼 **Advanced Chinese Bot**\n\n"
    "Send me Chinese characters and I will generate a beautiful image, "
    "provide Pinyin, translations, and high-quality Neural TTS audio!\n\n"
    "✨ **Features:**\n"
    "• 🖌️ **Fonts**: Multiple fonts including Calligraphy (KaiTi).\n"
    "• 📜 **Vertical**: Traditional top-to-bottom writing mode.\n"
    "• 🗣️ **Premium Audio**: Native-like Microsoft Edge TTS.\n\n"
    "🛠 **Commands:**\n"
)

def get_help_text() -> str:
    """Динамически генерирует текст для /help на основе списка команд."""
    text = FEATURES_TEXT
    for cmd in BOT_COMMANDS:
        text += f"👉 `/{cmd.command}` — {cmd.description}\n"
    return text
