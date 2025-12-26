import logging
import asyncio
import re
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ChatMemberHandler
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import TELEGRAM_TOKEN
from handlers.commands import (
    start, show_collections, show_collections_tsum,
    show_collection_status, handle_callback
)
from handlers.report_handler import handle_report_callback
from services.scheduler import StatusScheduler
from services.chat_manager import add_chat, remove_chat

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
    
    # Обработчик для автоматического добавления чатов при добавлении бота в группу
    async def handle_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает изменения статуса бота в чате"""
        try:
            if not update.my_chat_member:
                return
            
            chat = update.effective_chat
            new_status = update.my_chat_member.new_chat_member.status
            old_status = update.my_chat_member.old_chat_member.status
            
            logger.info(f"Bot status in chat {chat.id} ({chat.title}) changed from '{old_status}' to '{new_status}'")
            
            # Если бота добавили в группу/супергруппу
            if chat.type in ['group', 'supergroup']:
                if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
                    added_by = update.effective_user.id if update.effective_user else None
                    add_chat(chat.id, chat.title, added_by, chat.type)
                    logger.info(f"Chat {chat.id} ({chat.title}) automatically added to chats.json")
                
                # Если бота удалили из чата
                elif new_status in ['left', 'kicked']:
                    remove_chat(chat.id)
                    logger.info(f"Chat {chat.id} removed from chats.json")
        
        except Exception as e:
            logger.error(f"Error handling chat member update: {e}")
    
    # Обработчик для автоматического добавления чатов при первом сообщении в группе
    async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Автоматически добавляет чат при первом сообщении в группе"""
        try:
            chat = update.effective_chat
            if chat.type in ['group', 'supergroup']:
                from services.chat_manager import load_chats
                chats = load_chats()
                chat_id_str = str(chat.id)
                
                # Проверяем, есть ли уже такой чат
                if not any(str(c.get('chat_id')) == chat_id_str for c in chats):
                    added_by = update.effective_user.id if update.effective_user else None
                    add_chat(chat.id, chat.title, added_by, chat.type)
                    logger.info(f"Chat {chat.id} ({chat.title}) automatically added via first message")
        except Exception as e:
            logger.error(f"Error in handle_group_message: {e}")
    
    # Регистрируем обработчик изменений статуса бота в чате
    application.add_handler(ChatMemberHandler(handle_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # Регистрируем обработчик сообщений в группах для авто-добавления
    application.add_handler(MessageHandler(filters.ChatType.GROUPS, handle_group_message))
    
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
    application.run_polling(allowed_updates=["message", "callback_query", "my_chat_member"])

if __name__ == '__main__':
    main()

