from aiogram.types import BotCommand

BOT_COMMANDS = [
    BotCommand(command="settings", description="Open settings (Font, Color, Audio, Pushes)"),
    BotCommand(command="vocab",    description="View your saved vocabulary"),
    BotCommand(command="save",     description="Save a word: /save 你好 (or reply to a message)"),
    BotCommand(command="ch",       description="Generate image in groups: /ch 你好"),
    BotCommand(command="id",       description="Get your Telegram User ID for Web App sync"),
    BotCommand(command="progress", description="View synced Chinese study progress"),
    BotCommand(command="help",     description="Show help"),
]

FEATURES_TEXT = (
    "🐼 **Chinese Bot**\n\n"
    "Send Chinese characters — get a beautiful image, Pinyin, translations, and Neural TTS audio.\n"
    "Any other text is auto-translated to Chinese first.\n\n"
    "✨ **Features:**\n"
    "• 🖌️ **Fonts & Colors** — multiple styles, customisable.\n"
    "• 📜 **Vertical mode** — traditional top-to-bottom writing.\n"
    "• 🗣️ **TTS** — native-like Microsoft Edge Neural voice.\n"
    "• 💾 **Vocabulary** — save words, review anytime.\n"
    "• 📬 **Daily pushes** — bot sends words from your vocab at random times.\n\n"
    "🛠 **Commands:**\n"
)

def get_help_text() -> str:
    text = FEATURES_TEXT
    for cmd in BOT_COMMANDS:
        text += f"👉 /{cmd.command} — {cmd.description}\n"
    return text
