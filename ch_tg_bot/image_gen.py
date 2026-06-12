import io
import logging
import sys
from PIL import Image, ImageDraw, ImageFont
from aiogram.types import BufferedInputFile
from ch_tg_bot.config import FONT_FILES, FONT_SIZE

loaded_fonts = {}

def init_fonts():
    for key, info in FONT_FILES.items():
        try:
            loaded_fonts[key] = ImageFont.truetype(info["path"], FONT_SIZE)
        except IOError:
            logging.error(f"Font {info['path']} not found.")
    if not loaded_fonts:
        logging.error("No fonts loaded! Exiting.")
        sys.exit(1)

def text_to_image(text: str, font_key: str, color: str, vertical: bool) -> BufferedInputFile:
    font = loaded_fonts.get(font_key, list(loaded_fonts.values())[0])

    if vertical:
        chars = list(text.replace("\n", ""))
        char_boxes = [font.getbbox(c) for c in chars]
        max_w = max([b[2]-b[0] for b in char_boxes]) if char_boxes else 0

        img_width = max_w + 80
        img_height = sum([b[3]-b[1] + 20 for b in char_boxes]) + 80

        img = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(img)

        y_offset = 40
        for c in chars:
            bbox = draw.textbbox((0, 0), c, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x_offset = (img_width - w) / 2
            draw.text((x_offset, y_offset - bbox[1]), c, font=font, fill=color)
            y_offset += h + 20
    else:
        dummy_img = Image.new("RGB", (1, 1))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font)
        width = (bbox[2] - bbox[0]) + 80
        height = (bbox[3] - bbox[1]) + 80

        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        draw.multiline_text((40 - bbox[0], 40 - bbox[1]), text, font=font, fill=color)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return BufferedInputFile(buffer.getvalue(), filename="chinese.png")
