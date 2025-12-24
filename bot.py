import logging
import asyncio
import re
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config.settings import TELEGRAM_TOKEN
from handlers.commands import (
    start, help_command, show_collections, show_collections_tsum,
    show_collection_status, handle_callback
)
from handlers.report_handler import handle_report_callback
from services.scheduler import StatusScheduler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска бота"""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("collections", show_collections))
    application.add_handler(CommandHandler("collections_tsum", show_collections_tsum))
    application.add_handler(CommandHandler("status", show_collection_status))
    
    # Обработчик для сообщений с ID коллекции (UUID формат)
    async def handle_collection_id(update, context):
        """Обрабатывает сообщения с ID коллекции"""
        if update.message and update.message.text:
            text = update.message.text.strip()
            # Проверяем, является ли текст UUID
            uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            if re.match(uuid_pattern, text, re.IGNORECASE):
                # Это ID коллекции, запускаем сбор отчета
                await show_collection_status(update, context)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_collection_id))
    
    # Регистрируем обработчики callback
    # Сначала обрабатываем report_, потом остальные
    application.add_handler(CallbackQueryHandler(handle_report_callback, pattern="^report_"))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запускаем планировщик проверки статусов
    scheduler = StatusScheduler(application.bot)
    
    async def post_init(app: Application):
        """Функция, выполняемая после инициализации бота"""
        # Запускаем планировщик в фоне
        asyncio.create_task(scheduler.start())
        logger.info("Scheduler started")
    
    application.post_init = post_init
    
    # Запускаем бота
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == '__main__':
    main()

