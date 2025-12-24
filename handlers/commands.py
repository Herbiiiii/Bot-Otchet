import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from handlers.base import is_authorized_user
from services.bq_client import BigQueryClient
from services.status_tracker import StatusTracker
from config.settings import BIGQUERY_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON

logger = logging.getLogger(__name__)

def shorten_collection_name(name: str) -> str:
    """
    Сокращает название коллекции: первые 3 слова по первой букве
    Пример: "TSUM Collection Panel 10.12.2025" -> "TCP 10.12.2025"
    """
    if not name:
        return "Без названия"
    
    words = name.split()
    if len(words) <= 3:
        return name
    
    # Берем первые 3 слова и сокращаем по первой букве
    first_three = words[:3]
    shortened = ''.join([word[0].upper() if word else '' for word in first_three])
    
    # Остальные слова добавляем как есть
    rest = ' '.join(words[3:])
    if rest:
        return f"{shortened} {rest}"
    return shortened

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    # Проверяем, что это личное сообщение
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "❌ Команды бота доступны только в личных сообщениях.\n"
            "В беседах бот только отправляет автоматические отчеты."
        )
        try:
            await update.message.delete()
        except:
            pass
        return
    
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        await update.message.reply_text(
            "❌ У вас нет доступа к этому боту.\n"
            "Обратитесь к администратору для получения доступа."
        )
        try:
            await update.message.delete()
        except:
            pass
        return
    
    msg = await update.message.reply_text(
        "👋 Добро пожаловать в бот отчетов по коллекциям!\n\n"
        "Доступные команды:\n"
        "/collections - Показать все коллекции\n"
        "/collections_tsum - Показать коллекции со статусом 'tsum cs'\n"
        "/status <collection_id> - Показать статус коллекции\n"
        "/help - Справка"
    )
    
    try:
        await update.message.delete()
    except:
        pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    # Проверяем, что это личное сообщение
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "❌ Команды бота доступны только в личных сообщениях."
        )
        try:
            await update.message.delete()
        except:
            pass
        return
    
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        try:
            await update.message.delete()
        except:
            pass
        return
    
    msg = await update.message.reply_text(
        "📖 Справка по командам:\n\n"
        "/collections - Показать все коллекции компании tsum_cs\n"
        "/collections_tsum - Показать только коллекции со статусом 'tsum cs'\n"
        "/status <collection_id> - Показать детальную информацию о статусе коллекции\n"
        "/help - Показать эту справку"
    )
    
    try:
        await update.message.delete()
    except:
        pass

async def show_collections(update: Update, context: ContextTypes.DEFAULT_TYPE, filter_status: str = None, page: int = 0, edit_message=None):
    """Показывает список коллекций с пагинацией"""
    # Проверяем, что это личное сообщение
    if update.effective_chat.type != 'private':
        if update.message:
            await update.message.reply_text(
                "❌ Команды бота доступны только в личных сообщениях."
            )
            try:
                await update.message.delete()
            except:
                pass
        return
    
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        if update.message:
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            try:
                await update.message.delete()
            except:
                pass
        return
    
    try:
        # Инициализируем user_data если его нет
        if not hasattr(context, 'user_data'):
            context.user_data = {}
        
        # Сохраняем коллекции в context для пагинации
        if 'collections' not in context.user_data:
            loading_msg = None
            if edit_message:
                try:
                    await edit_message.edit_text("⏳ Загружаю коллекции...")
                    loading_msg = edit_message
                except:
                    loading_msg = await update.message.reply_text("⏳ Загружаю коллекции...")
            else:
                loading_msg = await update.message.reply_text("⏳ Загружаю коллекции...")
            
            bq_client = BigQueryClient(GOOGLE_APPLICATION_CREDENTIALS_JSON, BIGQUERY_PROJECT_ID)
            
            if filter_status:
                collections = bq_client.get_collections_with_status(filter_status)
                context.user_data['filter_status'] = filter_status
            else:
                collections = bq_client.get_all_collections()
                context.user_data['filter_status'] = None
            
            context.user_data['collections'] = collections
            context.user_data['loading_msg'] = loading_msg
            context.user_data['current_page'] = page
        else:
            collections = context.user_data['collections']
            filter_status = context.user_data.get('filter_status')
            loading_msg = context.user_data.get('loading_msg')
            context.user_data['current_page'] = page
        
        if not collections:
            if edit_message:
                await edit_message.edit_text("❌ Коллекции не найдены.")
            elif update.message:
                await update.message.reply_text("❌ Коллекции не найдены.")
            if update.message:
                try:
                    await update.message.delete()
                except:
                    pass
            return
        
        # Настройки пагинации
        ITEMS_PER_PAGE = 12  # По 12 коллекций на страницу (6 строк по 2 кнопки)
        total_pages = (len(collections) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        # Проверяем границы страницы
        if page < 0:
            page = 0
        if page >= total_pages:
            page = total_pages - 1
        
        # Получаем коллекции для текущей страницы
        start_idx = page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(collections))
        page_collections = collections[start_idx:end_idx]
        
        # Формируем клавиатуру с кнопками
        keyboard = []
        
        # Кнопки коллекций (по 2 в ряд)
        for i in range(0, len(page_collections), 2):
            row = []
            for j in range(2):
                if i + j < len(page_collections):
                    coll = page_collections[i + j]
                    name = coll.get('collection_name', 'Без названия')
                    # Сокращаем название
                    short_name = shorten_collection_name(name)
                    # Ограничиваем длину названия для кнопки
                    if len(short_name) > 25:
                        short_name = short_name[:22] + "..."
                    row.append(
                        InlineKeyboardButton(
                            short_name,
                            callback_data=f"coll_{coll['collection_id']}"
                        )
                    )
            keyboard.append(row)
        
        # Кнопки навигации
        nav_row = []
        
        # Кнопка "Предыдущая"
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ Предыдущая", callback_data=f"page_{page-1}_{filter_status or 'all'}"))
        
        # Кнопка с номером страницы
        nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Следующая ▶️", callback_data=f"page_{page+1}_{filter_status or 'all'}"))
        
        keyboard.append(nav_row)
        
        # Быстрые кнопки перехода на страницы (первые 5 страниц)
        if total_pages > 1:
            quick_nav = []
            max_quick_pages = min(5, total_pages)
            for p in range(max_quick_pages):
                if p != page:  # Не показываем текущую страницу
                    quick_nav.append(InlineKeyboardButton(str(p+1), callback_data=f"page_{p}_{filter_status or 'all'}"))
            if quick_nav:
                keyboard.append(quick_nav)
        
        # Кнопка "Обновить"
        keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="refresh_collections")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Формируем текст сообщения
        if filter_status:
            message_text = f"📋 Коллекции со статусом '{filter_status}':\n\n"
        else:
            message_text = "📋 Все коллекции:\n\n"
        
        message_text += f"Всего: {len(collections)} коллекций | Страница {page+1}/{total_pages}\n\n"
        
        # Показываем коллекции текущей страницы в тексте
        for idx, coll in enumerate(page_collections, start=start_idx+1):
            name = coll.get('collection_name', 'Без названия')
            short_name = shorten_collection_name(name)
            status = coll.get('status', 'не указан')
            coll_id = coll['collection_id']
            # Сокращаем ID для отображения
            short_id = coll_id[:12] + "..." if len(coll_id) > 16 else coll_id
            message_text += f"{idx}. {short_name}\n   ID: {short_id} | Статус: {status}\n\n"
        
        # Редактируем существующее сообщение или создаем новое
        if edit_message:
            try:
                await edit_message.edit_text(message_text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await edit_message.edit_text(message_text, reply_markup=reply_markup)
        elif loading_msg:
            try:
                await loading_msg.edit_text(message_text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Error editing loading message: {e}")
                await loading_msg.edit_text(message_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message_text, reply_markup=reply_markup)
        
        # Удаляем сообщение пользователя
        if update.message:
            try:
                await update.message.delete()
            except:
                pass
        
    except Exception as e:
        logger.error(f"Error showing collections: {e}")
        await update.message.reply_text(f"❌ Ошибка при загрузке коллекций: {str(e)}")

async def show_collections_tsum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает коллекции со статусом 'tsum cs'"""
    await show_collections(update, context, filter_status='tsum cs')

async def show_collection_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус конкретной коллекции и сразу начинает собирать отчет"""
    # Проверяем, что это личное сообщение
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "❌ Команды бота доступны только в личных сообщениях."
        )
        try:
            await update.message.delete()
        except:
            pass
        return
    
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        await update.message.reply_text("❌ У вас нет доступа к этому боту.")
        try:
            await update.message.delete()
        except:
            pass
        return
    
    try:
        # Получаем collection_id из аргументов команды или из текста сообщения
        collection_id = None
        
        if context.args and len(context.args) > 0:
            collection_id = context.args[0]
        elif update.message and update.message.text:
            # Пробуем извлечь ID из текста сообщения
            text = update.message.text.strip()
            # Если это UUID формат
            import re
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            match = re.search(uuid_pattern, text, re.IGNORECASE)
            if match:
                collection_id = match.group(0)
        
        if not collection_id:
            msg = await update.message.reply_text(
                "❌ Укажите ID коллекции.\n"
                "Пример: /status f01b63d4-90e6-49e7-a17a-1c6575a18450\n"
                "Или просто отправьте ID коллекции."
            )
            try:
                await update.message.delete()
            except:
                pass
            return
        
        # Сразу запускаем сбор отчета
        from handlers.report_handler import generate_report
        
        loading_msg = await update.message.reply_text(f"⏳ Загружаю информацию о коллекции {collection_id}...")
        
        try:
            await update.message.delete()
        except:
            pass
        
        # Запускаем сбор отчета
        await generate_report(update, context, collection_id, edit_message=loading_msg)
        
    except Exception as e:
        logger.error(f"Error showing collection status: {e}")
        import traceback
        logger.error(traceback.format_exc())
        if 'loading_msg' in locals():
            await loading_msg.edit_text(f"❌ Ошибка: {str(e)}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        if update.message:
            try:
                await update.message.delete()
            except:
                pass

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        await query.edit_message_text("❌ У вас нет доступа к этому боту.")
        return
    
    callback_data = query.data
    
    if callback_data.startswith("coll_"):
        # Показываем информацию о коллекции
        collection_id = callback_data.replace("coll_", "")
        await show_collection_info(query, collection_id, context)
    elif callback_data.startswith("page_"):
        # Обработка пагинации
        parts = callback_data.split("_")
        if len(parts) >= 3:
            try:
                page = int(parts[1])
                filter_status = parts[2] if parts[2] != 'all' else None
                
                # Очищаем кэш коллекций, чтобы загрузить заново
                if 'collections' in context.user_data:
                    del context.user_data['collections']
                
                # Сохраняем текущую страницу
                context.user_data['current_page'] = page
                # Показываем нужную страницу
                await show_collections(update, context, filter_status=filter_status, page=page, edit_message=query.message)
            except ValueError:
                await query.answer("Ошибка: неверный номер страницы", show_alert=True)
    elif callback_data == "page_info":
        # Просто показываем информацию о текущей странице
        await query.answer("Используйте кнопки навигации для перехода между страницами")
    elif callback_data == "back_to_list":
        # Возвращаемся к списку коллекций
        if not hasattr(context, 'user_data'):
            context.user_data = {}
        filter_status = context.user_data.get('filter_status')
        current_page = context.user_data.get('current_page', 0)
        await show_collections(update, context, filter_status=filter_status, page=current_page, edit_message=query.message)
    elif callback_data == "refresh_collections":
        # Обновляем список коллекций
        if 'collections' in context.user_data:
            del context.user_data['collections']
        await query.edit_message_text("⏳ Обновляю список коллекций...")
        filter_status = context.user_data.get('filter_status')
        await show_collections(update, context, filter_status=filter_status, page=0, edit_message=query.message)

async def show_collection_info(query, collection_id: str, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детальную информацию о коллекции и сразу начинает собирать отчет"""
    try:
        # Сразу начинаем собирать отчет
        from handlers.report_handler import generate_report
        from telegram import Update
        
        # Создаем фейковый update для передачи в generate_report
        class FakeUpdate:
            def __init__(self, msg):
                self.message = None
                self.effective_user = msg.from_user
                self.effective_chat = msg.chat
        
        fake_update = FakeUpdate(query.message)
        
        # Запускаем сбор отчета сразу
        await generate_report(fake_update, context, collection_id, edit_message=query.message)
        
    except Exception as e:
        logger.error(f"Error showing collection info: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

