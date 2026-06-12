# ch_tg_bot 🐼

Telegram-бот для изучения китайского языка. Генерирует изображения с китайскими иероглифами (поддерживает вертикальный режим, разные шрифты и цвета), озвучивает текст с помощью нейросетевого TTS от Microsoft Edge, автоматически переводит текст и помогает вести личный словарь с функцией интервальных напоминаний.

## Основные возможности 🌟

* **Красивые карточки-картинки** 🖌️ — бот генерирует каллиграфические изображения для отправленных слов/фраз. Поддерживаются разные цвета и каллиграфические шрифты.
* **Вертикальный режим** 📜 — поддержка традиционного китайского вертикального письма (сверху вниз, справа налево).
* **Качественная озвучка (TTS)** 🗣️ — озвучка текста носителем языка с помощью реалистичных нейросетевых голосов Microsoft Edge Neural.
* **Авто-перевод** 🔄 — если боту отправить русский или английский текст, он автоматически переведет его на китайский язык перед созданием карточки.
* **Личный словарь** 💾 — возможность сохранять иероглифы и фразы в личный словарь.
* **Ежедневные пуши** 📬 — автоматическая рассылка случайных слов из вашего словаря в течение дня для повторения и интервального обучения.

## Команды бота 🛠️

* `/settings` — настройки отображения (выбор шрифта, цвета, вертикального режима, включение/выключение пиньиня, перевода, TTS и частоты рассылки).
* `/vocab` — просмотр сохраненного словаря (с возможностью удаления слов).
* `/save <слово>` — сохранить китайское слово в словарь (или ответом на сообщение).
* `/ch <слово>` — сгенерировать карточку в групповом чате.
* `/help` — показать справку.

---

# ch_tg_bot 🐼 (English)

A Telegram bot designed to help you learn Chinese. It generates beautiful custom images from Chinese text (supporting vertical layout, different fonts, and colors), plays high-quality audio pronunciation using Microsoft Edge Neural TTS, auto-translates queries, and maintains a personal vocabulary list with daily spaced-repetition push notifications.

## Key Features 🌟

* **Beautiful Card Images** 🖌️ — Generates calligraphic images for Chinese words. Supports custom fonts (like Kaiti/Calligraphy, Serif, Sans-serif) and colors.
* **Vertical Mode** 📜 — Supports traditional Chinese top-to-bottom layout.
* **Neural TTS** 🗣️ — Native-like audio pronunciation utilizing Microsoft Edge's advanced neural voices.
* **Auto-Translation** 🔄 — If you send English or Russian text, the bot translates it to Chinese automatically.
* **Vocabulary Management** 💾 — Save words to your list directly from chat interface or using commands.
* **Daily Push Notifications** 📬 — Sends random words from your vocabulary list at set intervals between 09:00 and 22:00.

## Commands 🛠️

* `/settings` — Manage preferences (Fonts, Colors, Audio TTS, Languages, and Push frequencies).
* `/vocab` — List/manage your personal vocabulary list.
* `/save <word>` — Save a word to vocabulary (can be used as a reply to a message).
* `/ch <word>` — Generate word image in groups.
* `/help` — Show help message.

## Setup & Running 🚀

### Prerequisites
* Docker & Docker Compose
* Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Deployment
1. Clone the repository:
   ```bash
   git clone git@github.com:james19hadley/ch_tg_bot.git
   cd ch_tg_bot
   ```
2. Create a `.env` file in the root directory:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   ```
3. Run with Docker Compose:
   ```bash
   docker compose up -d --build
   ```
