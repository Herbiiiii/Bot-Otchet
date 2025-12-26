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
    
    # СНАЧАЛА показываем промежуточное сообщение сразу, чтобы пользователь видел реакцию
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
    
    try:
        # ТЕПЕРЬ получаем информацию о коллекции (после показа сообщения)
        import asyncio
        from services.bq_client import BigQueryClient
        from config.settings import BIGQUERY_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
        from handlers.commands import shorten_collection_name
        
        # Выполняем запрос к BigQuery в отдельном потоке, чтобы не блокировать event loop
        bq_client = BigQueryClient(GOOGLE_APPLICATION_CREDENTIALS_JSON, BIGQUERY_PROJECT_ID)
        collection = await asyncio.to_thread(bq_client.get_collection_by_id, collection_id)
        
        # Обновляем сообщение с информацией о коллекции, если она найдена
        if collection:
            collection_name = collection.get('collection_name', 'Без названия')
            short_name = shorten_collection_name(collection_name)
            status = collection.get('status', 'не указан')
            created_at = collection.get('created_at', 'Не указано')
            updated_at = collection.get('updated_at', 'Не указано')
            
            # Обновляем промежуточное сообщение с информацией о коллекции
            loading_text = (
                f"📊 Коллекция: {short_name}\n\n"
                f"ID: {collection_id}\n"
                f"Статус: {status}\n"
                f"Создана: {created_at}\n"
                f"Обновлена: {updated_at}\n\n"
                f"⏳ Собираю отчет... Это может занять некоторое время."
            )
            try:
                await loading_msg.edit_text(loading_text)
            except:
                pass
        
        # Проверяем, что email и password заданы
        if not ADMIN_EMAIL or not ADMIN_PASSWORD:
            error_msg = "❌ Не настроены учетные данные для входа в Мозаику. Проверьте ADMIN_EMAIL и ADMIN_PASSWORD в .env файле."
            await loading_msg.edit_text(error_msg)
            return
        
        # Выполняем тяжелые операции Selenium в отдельном потоке, чтобы не блокировать event loop
        def collect_report():
            """Синхронная функция для сбора отчета"""
            collector = SeleniumCollector(ADMIN_EMAIL, ADMIN_PASSWORD)
            try:
                # Входим в Мозаику
                if not collector.login():
                    return None, "❌ Не удалось войти в Мозаику. Проверьте учетные данные."
                
                # Собираем отчет
                report = collector.get_collection_report(collection_id)
                return report, None
            finally:
                collector.close()
        
        # Выполняем сбор отчета в отдельном потоке
        report, error_msg = await asyncio.to_thread(collect_report)
        
        if error_msg:
            await loading_msg.edit_text(error_msg)
            return
        
        if not report:
            error_msg = f"❌ Не удалось собрать отчет по коллекции {collection_id}."
            await loading_msg.edit_text(error_msg)
            return
        
        # Используем уже полученную информацию о коллекции
        if not collection:
            collection = await asyncio.to_thread(bq_client.get_collection_by_id, collection_id)
        
        collection_name = collection.get('collection_name', 'Без названия') if collection else 'Без названия'
        
        # Формируем ссылку в формате admin.dresscode.ai
        collection_url = f"https://admin.dresscode.ai/collection/{collection_id}"
        
        # Формируем сообщение с отчетом в формате как на фото
        # Формат:
        # "Добрый вечер!\n"
        # "\n"
        # "Направляем пак {полное название коллекции}\n"
        # "{ссылка}\n"
        # "\n"
        # "Статистика..."
        
        # Формируем сообщение с HTML форматированием для кликабельной ссылки
        # Экранируем специальные символы HTML в названии коллекции и делаем жирным
        from html import escape
        escaped_name = escape(collection_name)
        message = "Добрый вечер!\n"
        message += "\n"
        message += f"Направляем пак <b>{escaped_name}</b>\n"
        message += f"<a href=\"{collection_url}\">{collection_url}</a>\n"
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
        
        # Редактируем существующее сообщение с отчетом (используем HTML для кликабельной ссылки)
        await loading_msg.edit_text(message, parse_mode='HTML')
            
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
        # Используем query.from_user (пользователь, который нажал на кнопку), а не query.message.from_user (бот)
        class FakeUpdate:
            def __init__(self, query_obj):
                self.message = None
                self.effective_user = query_obj.from_user  # Пользователь, который нажал на кнопку
                self.effective_chat = query_obj.message.chat if query_obj.message else None
        
        fake_update = FakeUpdate(query)
        await generate_report(fake_update, context, collection_id, edit_message=query.message)

