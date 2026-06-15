import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiohttp import web
from ch_tg_bot.config import BOT_TOKEN
from ch_tg_bot.database import load_settings, update_user_progress
from ch_tg_bot.image_gen import init_fonts
from ch_tg_bot.handlers import router
from ch_tg_bot.commands import BOT_COMMANDS
from ch_tg_bot.scheduler import scheduler_loop

async def handle_progress_api(request):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    try:
        data = await request.json()
        user_id = data.get('user_id')
        streak = data.get('streak', 0)
        score = data.get('score', 0)
        lessons = data.get('lessons_completed', [])
        accuracy = data.get('accuracy', 0)

        if not user_id:
            return web.json_response({'error': 'user_id is required'}, status=400, headers={'Access-Control-Allow-Origin': '*'})

        # Convert to int in case it was passed as string
        user_id = int(user_id)

        update_user_progress(user_id, streak, score, lessons, accuracy)
        logging.info(f"API: Sync progress for user {user_id}")

        # Real-time progress push if configured and sharing is ON
        from ch_tg_bot.database import get_student_progress, get_progress_push_config
        student = get_student_progress(user_id)
        if student and student.get("share_progress"):
            config = get_progress_push_config(user_id)
            if config and config.get("chat_id"):
                bot = request.app['bot']
                from ch_tg_bot.handlers import format_progress_report
                report = format_progress_report(student)
                message_text = f"📈 *New Progress Update synced!*\n\n{report}"
                try:
                    await bot.send_message(
                        chat_id=config["chat_id"],
                        text=message_text,
                        message_thread_id=config.get("message_thread_id"),
                        parse_mode="Markdown"
                    )
                    logging.info(f"API: Pushed progress update for user {user_id} to chat {config['chat_id']}")
                except Exception as ex:
                    logging.error(f"API Error pushing update: {ex}")

        return web.json_response({'status': 'ok'}, headers={'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        logging.error(f"API Error: {e}")
        return web.json_response({'error': str(e)}, status=500, headers={'Access-Control-Allow-Origin': '*'})

async def handle_tts_api(request):
    if request.method == 'OPTIONS':
        return web.Response(headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        })
    text = request.query.get('text', '').strip()
    if not text:
        return web.json_response({'error': 'text is required'}, status=400, headers={'Access-Control-Allow-Origin': '*'})

    from ch_tg_bot.text_audio import get_tts_audio_bytes
    audio_data = await get_tts_audio_bytes(text)
    if not audio_data:
        return web.json_response({'error': 'failed to generate TTS'}, status=500, headers={'Access-Control-Allow-Origin': '*'})

    return web.Response(
        body=audio_data,
        content_type='audio/mpeg',
        headers={'Access-Control-Allow-Origin': '*'}
    )

async def start_http_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_route('*', '/api/progress', handle_progress_api)
    app.router.add_route('*', '/api/tts', handle_tts_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8090)
    await site.start()
    logging.info("HTTP API server started on http://0.0.0.0:8090")

async def main():
    logging.basicConfig(level=logging.INFO)
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not set!")
        return

    load_settings()
    init_fonts()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Запускаем HTTP сервер и планировщик ежедневных пушей в фоне
    asyncio.create_task(start_http_server(bot))
    asyncio.create_task(scheduler_loop(bot))

    # Автоматически обновляем меню команд в интерфейсе Telegram
    await bot.set_my_commands(BOT_COMMANDS)

    logging.info("Bot is starting...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
