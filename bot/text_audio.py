from pypinyin import pinyin, Style
from deep_translator import GoogleTranslator
import edge_tts
from aiogram.types import BufferedInputFile

def translate_to_chinese(text: str) -> str:
    """Translates non-Chinese text into Chinese."""
    try:
        return GoogleTranslator(source='auto', target='zh-CN').translate(text)
    except Exception:
        return text

def get_extra_info(text: str, show_pinyin: bool, show_ru: bool, show_en: bool) -> str:
    """Generates requested text info."""
    lines = []
    
    if show_pinyin:
        try:
            py = pinyin(text, style=Style.TONE)
            pinyin_text = " ".join([item[0] for item in py])
            lines.append(f"🗣 **Pinyin**: {pinyin_text}")
        except Exception:
            pass
            
    if show_ru:
        try:
            ru = GoogleTranslator(source='zh-CN', target='ru').translate(text)
            lines.append(f"🇷🇺 **RU**: {ru}")
        except Exception:
            pass
            
    if show_en:
        try:
            en = GoogleTranslator(source='zh-CN', target='en').translate(text)
            lines.append(f"🇬🇧 **EN**: {en}")
        except Exception:
            pass
            
    return "\n".join(lines)

async def get_tts_voice(text: str) -> BufferedInputFile:
    try:
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
