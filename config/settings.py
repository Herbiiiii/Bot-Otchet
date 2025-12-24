import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Telegram Bot
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Не задан TELEGRAM_TOKEN в .env файле")

TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'showoff_bot')

# BigQuery settings
BIGQUERY_PROJECT_ID = os.getenv('BIGQUERY_PROJECT_ID', 'looky-374212')
BIGQUERY_TABLE_COLLECTIONS = os.getenv('BIGQUERY_TABLE_COLLECTIONS', 'looky-374212.mosaica.showoff_custom_collections')
BIGQUERY_TABLE_ITEMS = os.getenv('BIGQUERY_TABLE_ITEMS', 'looky-374212.mosaica.showoff_custom_collections_items')
BIGQUERY_TABLE_ACTIONS = os.getenv('BIGQUERY_TABLE_ACTIONS', 'looky-374212.mosaica.showoff_operators_actions')

# Google Application Credentials (JSON строка)
# Может быть либо JSON строка, либо путь к файлу
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not GOOGLE_APPLICATION_CREDENTIALS_JSON:
    raise ValueError("Не задана переменная окружения GOOGLE_APPLICATION_CREDENTIALS")

# Если это путь к файлу, загружаем содержимое
if os.path.exists(GOOGLE_APPLICATION_CREDENTIALS_JSON) and os.path.isfile(GOOGLE_APPLICATION_CREDENTIALS_JSON):
    try:
        with open(GOOGLE_APPLICATION_CREDENTIALS_JSON, 'r', encoding='utf-8') as f:
            GOOGLE_APPLICATION_CREDENTIALS_JSON = f.read()
    except Exception as e:
        raise ValueError(f"Не удалось прочитать файл с учетными данными: {e}")

# Пробуем распарсить JSON для проверки валидности
try:
    import json
    json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)
except json.JSONDecodeError as e:
    raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS содержит невалидный JSON: {e}")

# Если это путь к файлу, загружаем содержимое
if os.path.exists(GOOGLE_APPLICATION_CREDENTIALS_JSON) and os.path.isfile(GOOGLE_APPLICATION_CREDENTIALS_JSON):
    try:
        with open(GOOGLE_APPLICATION_CREDENTIALS_JSON, 'r', encoding='utf-8') as f:
            GOOGLE_APPLICATION_CREDENTIALS_JSON = f.read()
    except Exception as e:
        raise ValueError(f"Не удалось прочитать файл с учетными данными: {e}")

# Mosaica credentials (используем EMAIL и PASSWORD_M из .env, как в Fast-track боте)
# ВАЖНО: Это учетные данные для входа в Мозаику, НЕ DressCode!
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL') or os.getenv('EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD') or os.getenv('PASSWORD_M')

# Пути к файлам данных
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / 'users.json'  # Список разрешенных пользователей
CHATS_FILE = DATA_DIR / 'chats.json'  # Список бесед для отправки отчетов
COLLECTIONS_STATUS_FILE = DATA_DIR / 'collections_status.json'  # Кэш статусов коллекций

# Создаем файлы, если их нет
if not USERS_FILE.exists():
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": []}, f, ensure_ascii=False, indent=2)

if not CHATS_FILE.exists():
    with open(CHATS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"chats": []}, f, ensure_ascii=False, indent=2)

if not COLLECTIONS_STATUS_FILE.exists():
    with open(COLLECTIONS_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"collections": {}}, f, ensure_ascii=False, indent=2)

# Настройки логирования
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'bot.log'

# Интервал проверки статусов коллекций (в секундах)
STATUS_CHECK_INTERVAL = int(os.getenv('STATUS_CHECK_INTERVAL', '60'))  # По умолчанию 60 секунд

# URL Мозаики
ADMIN_URL = "https://sandbox-prod.mosaica.ai"
MOSAICA_URL = "https://sandbox-prod.mosaica.ai"

# Прокси для BigQuery (опционально, можно отключить установив USE_PROXY=false)
USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
PROXY_SERVERS = [
    "net-157-22-102-218.mcccx.com:8444",
    "net-146-19-91-205.mcccx.com:8444",
    "net-185-88-103-247.mcccx.com:8444",
    "net-157-22-102-62.mcccx.com:8444",
    "net-147-78-182-237.mcccx.com:8444",
]

