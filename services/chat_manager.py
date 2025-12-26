import json
import logging
from pathlib import Path
from datetime import datetime
from config.settings import CHATS_FILE

logger = logging.getLogger(__name__)

def load_chats() -> list:
    """Загружает список чатов из файла"""
    try:
        chats_file = Path(CHATS_FILE)
        if not chats_file.exists():
            return []
        
        with open(chats_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('chats', [])
    except Exception as e:
        logger.error(f"Error loading chats: {e}")
        return []

def save_chats(chats: list) -> bool:
    """Сохраняет список чатов в файл"""
    try:
        chats_file = Path(CHATS_FILE)
        chats_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {'chats': chats}
        with open(chats_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving chats: {e}")
        return False

def add_chat(chat_id: int, chat_title: str, added_by: int = None, chat_type: str = None) -> bool:
    """
    Добавляет чат в список, если его там еще нет
    
    Args:
        chat_id: ID чата
        chat_title: Название чата
        added_by: ID пользователя, который добавил бота
        chat_type: Тип чата (group, supergroup, channel)
    
    Returns:
        True если чат был добавлен, False если уже был в списке
    """
    try:
        chats = load_chats()
        chat_id_str = str(chat_id)
        
        # Проверяем, есть ли уже такой чат
        for chat in chats:
            if str(chat.get('chat_id')) == chat_id_str:
                logger.info(f"Chat {chat_id} already in list")
                return False
        
        # Добавляем новый чат
        new_chat = {
            'chat_id': chat_id_str,
            'title': chat_title or 'Без названия',
            'added_by': str(added_by) if added_by else None,
            'added_at': datetime.now().isoformat(),
            'is_active': True
        }
        
        chats.append(new_chat)
        
        if save_chats(chats):
            logger.info(f"Chat {chat_id} ({chat_title}) added to chats.json")
            return True
        else:
            logger.error(f"Failed to save chat {chat_id} to chats.json")
            return False
            
    except Exception as e:
        logger.error(f"Error adding chat: {e}")
        return False

def remove_chat(chat_id: int) -> bool:
    """Удаляет чат из списка"""
    try:
        chats = load_chats()
        chat_id_str = str(chat_id)
        
        # Удаляем чат из списка
        chats = [chat for chat in chats if str(chat.get('chat_id')) != chat_id_str]
        
        if save_chats(chats):
            logger.info(f"Chat {chat_id} removed from chats.json")
            return True
        else:
            logger.error(f"Failed to remove chat {chat_id} from chats.json")
            return False
            
    except Exception as e:
        logger.error(f"Error removing chat: {e}")
        return False

def get_active_chats() -> list:
    """Возвращает список активных чатов"""
    chats = load_chats()
    return [chat for chat in chats if chat.get('is_active', True)]

