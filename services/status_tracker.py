import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from config.settings import COLLECTIONS_STATUS_FILE, BIGQUERY_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS_JSON
from services.bq_client import BigQueryClient

logger = logging.getLogger(__name__)

class StatusTracker:
    """Класс для отслеживания изменений статусов коллекций"""
    
    def __init__(self):
        """Инициализация трекера"""
        self.bq_client = BigQueryClient(GOOGLE_APPLICATION_CREDENTIALS_JSON, BIGQUERY_PROJECT_ID)
        self.status_file = Path(COLLECTIONS_STATUS_FILE)
        self._load_cached_statuses()
        # Флаг для отслеживания первой загрузки (чтобы не отправлять отчеты при перезапуске)
        self.is_first_run = len(self.cached_statuses) == 0
    
    def _load_cached_statuses(self):
        """Загружает кэшированные статусы из файла"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cached_statuses = data.get('collections', {})
            else:
                self.cached_statuses = {}
            logger.info(f"Loaded {len(self.cached_statuses)} cached collection statuses")
        except Exception as e:
            logger.error(f"Error loading cached statuses: {e}")
            self.cached_statuses = {}
    
    def _save_cached_statuses(self):
        """Сохраняет статусы в файл"""
        try:
            data = {'collections': self.cached_statuses}
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving cached statuses: {e}")
    
    def check_status_changes(self) -> List[Dict]:
        """
        Проверяет изменения статусов коллекций
        
        Returns:
            Список коллекций, у которых статус изменился на 'tsum cs'
        """
        try:
            # Получаем ТОЛЬКО коллекции со статусом 'tsum cs' из BigQuery
            collections = self.bq_client.get_collections_with_status('tsum cs')
            
            changed_collections = []
            
            # Получаем список ID коллекций со статусом 'tsum cs' для очистки кэша
            tsum_cs_collection_ids = {col['collection_id'] for col in collections}
            
            for collection in collections:
                collection_id = collection['collection_id']
                current_status = collection.get('status', '') or ''
                
                # Проверяем, был ли изменен статус на 'tsum cs'
                cached_status = self.cached_statuses.get(collection_id, {}).get('status', '') or ''
                
                # Нормализуем статусы для сравнения
                current_status_normalized = current_status.strip().lower()
                cached_status_normalized = cached_status.strip().lower()
                
                # Если это первый запуск (кэш был пустой), просто обновляем кэш без отправки отчетов
                if self.is_first_run:
                    logger.info(f"First run: caching collection {collection_id} ({collection.get('collection_name', '')}) with status 'tsum cs'")
                elif current_status_normalized == 'tsum cs' and cached_status_normalized != 'tsum cs':
                    # Статус изменился на 'tsum cs' (и это не первый запуск)
                    changed_collections.append(collection)
                    logger.info(f"Collection {collection_id} ({collection.get('collection_name', '')}) status changed to 'tsum cs'")
                
                # Обновляем кэш ТОЛЬКО для коллекций со статусом 'tsum cs'
                self.cached_statuses[collection_id] = {
                    'status': current_status,
                    'collection_name': collection.get('collection_name', ''),
                    'last_checked': datetime.now().isoformat()
                }
            
            # После первой проверки сбрасываем флаг
            if self.is_first_run:
                self.is_first_run = False
                logger.info("First run completed, cache initialized. Future status changes will trigger reports.")
            
            # Удаляем из кэша коллекции, которые больше не имеют статус 'tsum cs'
            # (чтобы не накапливались коллекции без статуса)
            collections_to_remove = []
            for collection_id in self.cached_statuses.keys():
                if collection_id not in tsum_cs_collection_ids:
                    collections_to_remove.append(collection_id)
            
            for collection_id in collections_to_remove:
                del self.cached_statuses[collection_id]
                logger.debug(f"Removed collection {collection_id} from cache (no longer 'tsum cs')")
            
            # Сохраняем обновленные статусы
            self._save_cached_statuses()
            
            return changed_collections
            
        except Exception as e:
            logger.error(f"Error checking status changes: {e}")
            return []
    
    def get_collection_status(self, collection_id: str) -> Optional[str]:
        """
        Получает текущий статус коллекции
        
        Args:
            collection_id: ID коллекции
        
        Returns:
            Статус коллекции или None
        """
        try:
            collection = self.bq_client.get_collection_by_id(collection_id)
            if collection:
                return collection.get('status')
            return None
        except Exception as e:
            logger.error(f"Error getting collection status: {e}")
            return None

