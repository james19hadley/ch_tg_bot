import io
from pypinyin import pinyin, Style
from deep_translator import GoogleTranslator
from gtts import gTTS
from aiogram.types import BufferedInputFile

def get_pinyin_and_translation(text: str):
    try:
        py = pinyin(text, style=Style.TONE)
        pinyin_text = " ".join([item[0] for item in py])
        translation_ru = GoogleTranslator(source='zh-CN', target='ru').translate(text)
        translation_en = GoogleTranslator(source='zh-CN', target='en').translate(text)
        return f"🗣 **Pinyin**: {pinyin_text}\n🇷🇺 **RU**: {translation_ru}\n🇬🇧 **EN**: {translation_en}"
    except Exception:
        return ""

def get_tts_voice(text: str) -> BufferedInputFile:
    try:
        tts = gTTS(text, lang='zh-CN')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return BufferedInputFile(fp.getvalue(), filename="voice.ogg")
    except Exception:
        return None
