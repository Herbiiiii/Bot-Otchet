import asyncio
import logging
from telegram import Bot
from services.status_tracker import StatusTracker
from services.report_sender import ReportSender
from config.settings import STATUS_CHECK_INTERVAL, TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

class StatusScheduler:
    """Планировщик для проверки изменений статусов и отправки отчетов"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация планировщика
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
        self.tracker = StatusTracker()
        self.report_sender = ReportSender(bot)
        self.is_running = False
    
    async def start(self):
        """Запускает планировщик"""
        self.is_running = True
        logger.info("Status scheduler started")
        
        while self.is_running:
            try:
                # Проверяем изменения статусов
                changed_collections = self.tracker.check_status_changes()
                
                # Для каждой коллекции со статусом 'tsum cs' отправляем отчет
                for collection in changed_collections:
                    if collection.get('status') == 'tsum cs':
                        collection_id = collection.get('collection_id')
                        collection_name = collection.get('collection_name', '')
                        
                        logger.info(f"Sending report for collection {collection_id} ({collection_name})")
                        await self.report_sender.send_report_to_chats(collection_id, collection_name)
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(STATUS_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in status scheduler: {e}")
                await asyncio.sleep(STATUS_CHECK_INTERVAL)
    
    def stop(self):
        """Останавливает планировщик"""
        self.is_running = False
        logger.info("Status scheduler stopped")



