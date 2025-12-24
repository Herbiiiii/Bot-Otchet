import logging
from telegram import Update
from telegram.ext import ContextTypes
from handlers.base import is_authorized_user
from services.selenium_collector import SeleniumCollector
from config.settings import ADMIN_EMAIL, ADMIN_PASSWORD

logger = logging.getLogger(__name__)

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE, collection_id: str, edit_message=None):
    """
    Генерирует отчет по коллекции через Selenium
    
    Args:
        update: Обновление от Telegram
        context: Контекст бота
        collection_id: ID коллекции
        edit_message: Сообщение для редактирования (опционально)
    """
    # Проверяем, что это личное сообщение (если есть chat)
    if hasattr(update, 'effective_chat') and update.effective_chat and update.effective_chat.type != 'private':
        if update.message:
            await update.message.reply_text(
                "❌ Команды бота доступны только в личных сообщениях."
            )
            try:
                await update.message.delete()
            except:
                pass
        return
    
    # Проверяем авторизацию пользователя
    if hasattr(update, 'effective_user') and update.effective_user:
        user_id = update.effective_user.id
        logger.info(f"Checking authorization for user {user_id}")
        
        if not is_authorized_user(user_id):
            error_msg = f"❌ У вас нет доступа к этому боту. Ваш ID: {user_id}"
            if edit_message:
                await edit_message.edit_text(error_msg)
            elif update.message:
                await update.message.reply_text(error_msg)
                try:
                    await update.message.delete()
                except:
                    pass
            return
    
    try:
        # Получаем информацию о коллекции для промежуточного сообщения
        from services.bq_client import BigQueryClient
        from config.settings import BIGQUERY_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
        from handlers.commands import shorten_collection_name
        
        bq_client = BigQueryClient(GOOGLE_APPLICATION_CREDENTIALS_JSON, BIGQUERY_PROJECT_ID)
        collection = bq_client.get_collection_by_id(collection_id)
        
        if collection:
            collection_name = collection.get('collection_name', 'Без названия')
            short_name = shorten_collection_name(collection_name)
            status = collection.get('status', 'не указан')
            created_at = collection.get('created_at', 'Не указано')
            updated_at = collection.get('updated_at', 'Не указано')
            
            # Формируем промежуточное сообщение с информацией о коллекции
            loading_text = (
                f"📊 Коллекция: {short_name}\n\n"
                f"ID: {collection_id}\n"
                f"Статус: {status}\n"
                f"Создана: {created_at}\n"
                f"Обновлена: {updated_at}\n\n"
                f"⏳ Собираю отчет... Это может занять некоторое время."
            )
        else:
            loading_text = f"⏳ Собираю отчет по коллекции {collection_id}...\nЭто может занять некоторое время."
        
        if edit_message:
            try:
                await edit_message.edit_text(loading_text)
                loading_msg = edit_message
            except:
                if update.message:
                    loading_msg = await update.message.reply_text(loading_text)
                else:
                    return
        elif update.message:
            loading_msg = await update.message.reply_text(loading_text)
            try:
                await update.message.delete()
            except:
                pass
        else:
            return
        
        # Проверяем, что email и password заданы
        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            error_msg = "❌ Не настроены учетные данные для входа в Мозаику. Проверьте ADMIN_EMAIL и ADMIN_PASSWORD в .env файле."
            await loading_msg.edit_text(error_msg)
            return
        
        # Инициализируем Selenium коллектор
        collector = SeleniumCollector(ADMIN_EMAIL, ADMIN_PASSWORD)
        
        try:
            # Входим в Мозаику
            if not collector.login():
                error_msg = "❌ Не удалось войти в Мозаику. Проверьте учетные данные."
                await loading_msg.edit_text(error_msg)
                return
            
            # Собираем отчет
            report = collector.get_collection_report(collection_id)
            
            if not report:
                error_msg = f"❌ Не удалось собрать отчет по коллекции {collection_id}."
                await loading_msg.edit_text(error_msg)
                return
            
            # Используем уже полученную информацию о коллекции
            if not collection:
                collection = bq_client.get_collection_by_id(collection_id)
            
            collection_name = collection.get('collection_name', 'Без названия') if collection else 'Без названия'
            
            # Формируем ссылку в формате catalog.dresscode.ai
            collection_url = f"https://catalog.dresscode.ai/collection/{collection_id}"
            # Если в отчете есть ссылка и она не tsum.ru, используем её
            if report.get('collection_url') and 'tsum.ru' not in report.get('collection_url', '').lower():
                collection_url = report['collection_url']
            
            # Формируем сообщение с отчетом в формате как на фото
            # Формат:
            # "Добрый вечер!\n"
            # "\n"
            # "Направляем пак {полное название коллекции}\n"
            # "{ссылка}\n"
            # "\n"
            # "Статистика..."
            
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
            
            # Редактируем существующее сообщение с отчетом
            await loading_msg.edit_text(message)
            
        finally:
            collector.close()
            
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        error_msg = f"❌ Ошибка при генерации отчета: {str(e)}"
        if edit_message:
            await edit_message.edit_text(error_msg)
        elif 'loading_msg' in locals():
            await loading_msg.edit_text(error_msg)
        elif update.message:
            await update.message.reply_text(error_msg)

async def handle_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для генерации отчета"""
    query = update.callback_query
    await query.answer()
    
    if query.data and query.data.startswith("report_"):
        collection_id = query.data.replace("report_", "")
        # Используем query.message вместо update.message для callback
        class FakeUpdate:
            def __init__(self, msg):
                self.message = None
                self.effective_user = msg.from_user
                self.effective_chat = msg.chat
        
        fake_update = FakeUpdate(query.message)
        await generate_report(fake_update, context, collection_id, edit_message=query.message)

