FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# Создаем папку для шрифтов и качаем 7 разных вариантов
RUN mkdir -p fonts && \
    wget -q -O fonts/Sans-Thin.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Thin.otf" && \
    wget -q -O fonts/Sans-Light.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Light.otf" && \
    wget -q -O fonts/Sans-Regular.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" && \
    wget -q -O fonts/Sans-Medium.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Medium.otf" && \
    wget -q -O fonts/Sans-Bold.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf" && \
    wget -q -O fonts/Sans-Black.otf "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Black.otf" && \
    wget -q -O fonts/Serif-Regular.otf "https://github.com/notofonts/noto-cjk/raw/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]