import json
import os
from google.cloud import bigquery
from google.oauth2 import service_account
from typing import List, Dict, Optional
import logging
import traceback
import random

logger = logging.getLogger(__name__)

class BigQueryClient:
    """Клиент для работы с BigQuery"""
    
    def __init__(self, credentials_json: str, project_id: str):
        """
        Инициализация клиента BigQuery
        
        Args:
            credentials_json: JSON строка с учетными данными сервисного аккаунта
            project_id: ID проекта Google Cloud
        """
        try:
            # Пробуем сначала распарсить как JSON строку
            credentials_dict = None
            
            # Если это уже словарь
            if isinstance(credentials_json, dict):
                credentials_dict = credentials_json
            # Если это путь к файлу
            elif os.path.exists(credentials_json) and os.path.isfile(credentials_json):
                with open(credentials_json, 'r', encoding='utf-8') as f:
                    credentials_dict = json.load(f)
            else:
                # Пробуем распарсить как JSON строку
                try:
                    credentials_dict = json.loads(credentials_json)
                except json.JSONDecodeError as e:
                    # Если не получилось, пробуем обработать экранированные символы
                    # В .env файлах могут быть двойные экранирования
                    try:
                        # Заменяем \\n на \n для правильной обработки переносов строк
                        processed_json = credentials_json.replace('\\n', '\n').replace('\\\\', '\\')
                        credentials_dict = json.loads(processed_json)
                    except Exception as e2:
                        logger.error(f"JSON decode error: {e}")
                        logger.error(f"Second attempt error: {e2}")
                        logger.error(f"First 200 chars of credentials: {credentials_json[:200]}")
                        raise ValueError(f"Не удалось распарсить JSON из GOOGLE_APPLICATION_CREDENTIALS: {e}")
            
            # Важно: исправляем private_key - заменяем \\n на реальные переносы строк
            if credentials_dict and 'private_key' in credentials_dict:
                private_key = credentials_dict['private_key']
                if isinstance(private_key, str):
                    # Пробуем разные варианты замены переносов строк
                    original_key = private_key
                    original_length = len(private_key)
                    
                    # Вариант 1: \\\\n -> \n (двойное экранирование в .env - проверяем сначала)
                    if '\\\\n' in private_key:
                        private_key = private_key.replace('\\\\n', '\n')
                        logger.debug(f"Replaced \\\\n with actual newline in private_key (length: {original_length} -> {len(private_key)})")
                    
                    # Вариант 2: \\n -> \n (стандартное экранирование)
                    elif '\\n' in private_key:
                        private_key = private_key.replace('\\n', '\n')
                        logger.debug(f"Replaced \\n with actual newline in private_key (length: {original_length} -> {len(private_key)})")
                    
                    # Убираем лишние пробелы в начале/конце, но сохраняем переносы строк
                    private_key = private_key.strip()
                    
                    # Проверяем длину - приватный ключ должен быть длинным (обычно > 1000 символов)
                    if len(private_key) < 100:
                        logger.error(f"Private key seems too short: {len(private_key)} characters. Original length was {original_length}")
                        logger.error(f"First 100 chars: {original_key[:100]}")
                        logger.error(f"Last 100 chars: {original_key[-100:]}")
                        raise ValueError(f"Private key is too short ({len(private_key)} chars). Check JSON parsing in .env file.")
                    
                    # Проверяем, что ключ начинается правильно
                    if not private_key.startswith('-----BEGIN'):
                        logger.warning("Private key doesn't start with -----BEGIN, trying to fix...")
                        # Пробуем найти начало ключа
                        begin_idx = private_key.find('-----BEGIN')
                        if begin_idx != -1:
                            private_key = private_key[begin_idx:]
                        else:
                            logger.error("Could not find -----BEGIN in private_key")
                            raise ValueError("Invalid private_key format: missing -----BEGIN")
                    
                    # Проверяем, что ключ заканчивается правильно
                    if not private_key.endswith('-----END PRIVATE KEY-----'):
                        # Пробуем найти конец ключа
                        end_idx = private_key.rfind('-----END PRIVATE KEY-----')
                        if end_idx != -1:
                            private_key = private_key[:end_idx + len('-----END PRIVATE KEY-----')]
                        else:
                            logger.warning("Could not find proper end of private_key")
                    
                    credentials_dict['private_key'] = private_key
                    logger.info(f"Private key processed: length={len(private_key)}, starts={private_key[:30]}..., ends={private_key[-30:]}")
            
            # Создаем credentials объект
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict
            )
            
            # Настройка прокси для BigQuery (если нужен)
            from config.settings import USE_PROXY, PROXY_SERVERS
            
            if USE_PROXY and PROXY_SERVERS:
                try:
                    # Выбираем случайный прокси
                    proxy = random.choice(PROXY_SERVERS)
                    proxy_url = f"http://{proxy}"
                    
                    # Устанавливаем переменные окружения для прокси
                    os.environ['HTTP_PROXY'] = proxy_url
                    os.environ['HTTPS_PROXY'] = proxy_url
                    os.environ['http_proxy'] = proxy_url
                    os.environ['https_proxy'] = proxy_url
                    
                    logger.info(f"Using proxy for BigQuery: {proxy}")
                except Exception as e:
                    logger.warning(f"Failed to set up proxy: {e}, continuing without proxy")
            else:
                logger.info("Proxy disabled or not configured, using direct connection")
            
            # Инициализируем клиент
            self.client = bigquery.Client(credentials=credentials, project=project_id)
            logger.info("BigQuery client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def get_collections_with_status(self, status: str = 'tsum cs') -> List[Dict]:
        """
        Получает список коллекций с указанным статусом
        
        Args:
            status: Статус коллекции для фильтрации (по умолчанию 'tsum cs')
        
        Returns:
            Список словарей с информацией о коллекциях
        """
        from config.settings import BIGQUERY_TABLE_COLLECTIONS
        
        # Получаем коллекции с фильтрацией по названию (TSUM Collection Panel)
        query = f"""
        SELECT 
            collection_id,
            collection_name,
            company_id,
            created_at,
            updated_at
        FROM `{BIGQUERY_TABLE_COLLECTIONS}`
        WHERE company_id = 'tsum_cs'
        AND collection_name LIKE '%TSUM Collection Panel%'
        ORDER BY created_at DESC
        """
        
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            collections = []
            for row in results:
                # Определяем статус по названию коллекции
                collection_name = row.collection_name or ''
                # Если в названии есть "TSUM Collection Panel", считаем статус "tsum cs"
                collection_status = 'tsum cs' if 'TSUM Collection Panel' in collection_name else ''
                
                collections.append({
                    'collection_id': row.collection_id,
                    'collection_name': row.collection_name,
                    'company_id': row.company_id,
                    'status': collection_status,
                    'created_at': str(row.created_at) if row.created_at else None,
                    'updated_at': str(row.updated_at) if row.updated_at else None,
                })
            
            logger.info(f"Found {len(collections)} collections with status '{status}'")
            return collections
            
        except Exception as e:
            logger.error(f"Error getting collections: {e}")
            return []
    
    def get_all_collections(self) -> List[Dict]:
        """
        Получает ВСЕ коллекции из базы данных (без фильтров)
        
        Returns:
            Список словарей с информацией о коллекциях
        """
        from config.settings import BIGQUERY_TABLE_COLLECTIONS
        
        query = f"""
        SELECT 
            collection_id,
            collection_name,
            company_id,
            created_at,
            updated_at
        FROM `{BIGQUERY_TABLE_COLLECTIONS}`
        ORDER BY created_at DESC
        """
        
        try:
            query_job = self.client.query(query)
            results = query_job.result()
            
            collections = []
            for row in results:
                # Определяем статус по названию коллекции
                collection_name = row.collection_name or ''
                # Если в названии есть "TSUM Collection Panel", считаем статус "tsum cs"
                collection_status = 'tsum cs' if 'TSUM Collection Panel' in collection_name else ''
                
                collections.append({
                    'collection_id': row.collection_id,
                    'collection_name': row.collection_name,
                    'company_id': row.company_id,
                    'status': collection_status,
                    'created_at': str(row.created_at) if row.created_at else None,
                    'updated_at': str(row.updated_at) if row.updated_at else None,
                })
            
            logger.info(f"Found {len(collections)} collections")
            return collections
            
        except Exception as e:
            logger.error(f"Error getting all collections: {e}")
            return []
    
    def get_collection_by_id(self, collection_id: str) -> Optional[Dict]:
        """
        Получает информацию о коллекции по ID
        
        Args:
            collection_id: ID коллекции
        
        Returns:
            Словарь с информацией о коллекции или None
        """
        from config.settings import BIGQUERY_TABLE_COLLECTIONS
        
        query = f"""
        SELECT 
            collection_id,
            collection_name,
            company_id,
            created_at,
            updated_at
        FROM `{BIGQUERY_TABLE_COLLECTIONS}`
        WHERE collection_id = @collection_id
        LIMIT 1
        """
        
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                # Определяем статус по названию коллекции
                collection_name = row.collection_name or ''
                status = 'tsum cs' if 'tsum' in collection_name.lower() and 'cs' in collection_name.lower() else ''
                
                return {
                    'collection_id': row.collection_id,
                    'collection_name': row.collection_name,
                    'company_id': row.company_id,
                    'status': status,
                    'created_at': str(row.created_at) if row.created_at else None,
                    'updated_at': str(row.updated_at) if row.updated_at else None,
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting collection by ID: {e}")
            return None

