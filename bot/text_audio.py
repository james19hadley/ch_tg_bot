import io
from pypinyin import pinyin, Style
from deep_translator import GoogleTranslator
import edge_tts
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

async def get_tts_voice(text: str) -> BufferedInputFile:
    try:
        # Используем нейросетевой голос от Microsoft Azure
        voice = "zh-CN-XiaoxiaoNeural"
        communicate = edge_tts.Communicate(text, voice)
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
                
        if not audio_data:
            return None
            
        return BufferedInputFile(audio_data, filename="voice.mp3")
    except Exception as e:
        print(f"TTS Error: {e}")
        return None
