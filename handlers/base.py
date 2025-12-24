import json
import logging
from pathlib import Path
from config.settings import USERS_FILE

logger = logging.getLogger(__name__)

def is_authorized_user(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь авторизованным (только менеджеры)
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        True если пользователь является менеджером, False в противном случае
    """
    try:
        users_file = Path(USERS_FILE)
        if not users_file.exists():
            logger.warning("Users file does not exist")
            return False
        
        with open(users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            users = data.get('users', [])
            
            # Проверяем, есть ли пользователь в списке и является ли он менеджером
            for user in users:
                # Поддерживаем оба формата: telegram_id и user_id
                user_telegram_id = user.get('telegram_id') or user.get('user_id')
                if user_telegram_id and int(user_telegram_id) == user_id:
                    # Проверяем статус - только менеджеры могут пользоваться ботом
                    user_status = user.get('status', '').lower()
                    if user_status == 'manager':
                        return True
                    else:
                        logger.info(f"User {user_id} is not a manager (status: {user_status})")
                        return False
            
            logger.info(f"User {user_id} not found in users list")
            return False
            
    except Exception as e:
        logger.error(f"Error checking user authorization: {e}")
        return False

def get_user_info(user_id: int) -> dict:
    """
    Получает информацию о пользователе
    
    Args:
        user_id: ID пользователя Telegram
    
    Returns:
        Словарь с информацией о пользователе
    """
    try:
        users_file = Path(USERS_FILE)
        if not users_file.exists():
            return {}
        
        with open(users_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            users = data.get('users', [])
            
            for user in users:
                # Поддерживаем оба формата: telegram_id и user_id
                user_telegram_id = user.get('telegram_id') or user.get('user_id')
                if user_telegram_id and int(user_telegram_id) == user_id:
                    return user
            
            return {}
            
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return {}

