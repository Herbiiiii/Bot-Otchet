import logging
from typing import List, Dict
from telegram import Bot
from services.selenium_collector import SeleniumCollector
from services.bq_client import BigQueryClient
from config.settings import ADMIN_EMAIL, ADMIN_PASSWORD, BIGQUERY_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
from services.chat_manager import get_active_chats

logger = logging.getLogger(__name__)

class ReportSender:
    """Класс для отправки отчетов в беседы"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация отправителя отчетов
        
        Args:
            bot: Экземпляр Telegram бота
        """
        self.bot = bot
    
    async def send_report_to_chats(self, collection_id: str, collection_name: str = None):
        """
        Отправляет отчет по коллекции во все активные беседы
        
        Args:
            collection_id: ID коллекции
            collection_name: Название коллекции (опционально)
        """
        try:
            # Собираем отчет через Selenium
            collector = SeleniumCollector(ADMIN_EMAIL, ADMIN_PASSWORD)
            
            try:
                if not collector.login():
                    logger.error("Failed to login to admin panel")
                    return
                
                report = collector.get_collection_report(collection_id)
                
                if not report:
                    logger.error(f"Failed to get report for collection {collection_id}")
                    return
                
                # Формируем сообщение в том же формате, что и ручной вызов
                # Формат:
                # "Добрый вечер!\n"
                # "\n"
                # "Направляем пак {полное название коллекции}\n"
                # "{ссылка}\n"
                # "\n"
                # "Статистика..."
                
                # Используем переданное название или получаем из отчета
                if not collection_name:
                    collection_name = report.get('collection_name', 'Без названия')
                
                # Формируем ссылку
                collection_url = f"https://catalog.dresscode.ai/collection/{collection_id}"
                if report.get('collection_url') and 'tsum.ru' not in report.get('collection_url', '').lower():
                    collection_url = report['collection_url']
                
                # Формируем сообщение
                message = "Добрый вечер!\n"
                message += "\n"
                message += f"Направляем пак {collection_name}\n"
                message += f"{collection_url}\n"
                message += "\n"
                
                # Добавляем статистику
                total_done = report.get('total_done', 0) or 0
                combo_items = report.get('combo_items', 0) or 0
                
                if total_done:
                    message += f"Общее количество уникальных done-айтемов - {total_done}\n"
                
                if combo_items:
                    message += f"Из них combo-айтемов – {combo_items}\n"
                
                # Рассчитываем "Итого total done" = total_done + combo_items
                total_done_items = total_done + combo_items
                if total_done_items > 0:
                    message += f"Итого total done - {total_done_items} айтемов"
                
                # Отправляем во все активные беседы
                chats = get_active_chats()
                
                for chat in chats:
                    chat_id = chat.get('chat_id')
                    if not chat_id:
                        continue
                    
                    try:
                        await self.bot.send_message(
                            chat_id=int(chat_id),
                            text=message
                        )
                        logger.info(f"Report sent to chat {chat_id}")
                    except Exception as e:
                        logger.error(f"Error sending report to chat {chat_id}: {e}")
                
            finally:
                collector.close()
                
        except Exception as e:
            logger.error(f"Error sending report to chats: {e}")

