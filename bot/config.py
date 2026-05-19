import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data/settings.json"
FONT_SIZE = 150
MAX_TEXT_LENGTH = 100

FONT_FILES = {
    "sans_regular": {"path": "fonts/Sans-Regular.otf", "name": "Sans Regular"},
    "sans_bold": {"path": "fonts/Sans-Bold.otf", "name": "Sans Bold"},
    "serif_regular": {"path": "fonts/Serif-Regular.otf", "name": "Serif Classic"},
    "kaiti": {"path": "fonts/MaShanZheng-Regular.ttf", "name": "Calligraphy"},
}
DEFAULT_FONT = "sans_regular"
