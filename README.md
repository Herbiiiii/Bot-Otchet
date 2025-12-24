# Bot-stats - Бот для отслеживания статусов коллекций и генерации отчетов

Бот для автоматического отслеживания статусов коллекций в BigQuery и генерации отчетов через Selenium.

## Функционал

- ✅ Отслеживание изменений статусов коллекций в BigQuery
- ✅ Автоматическая генерация отчетов через Selenium при изменении статуса на "tsum cs"
- ✅ Отправка отчетов в указанные беседы Telegram
- ✅ Защита доступа (только авторизованные пользователи)
- ✅ Команды для просмотра коллекций и их статусов

## Установка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Создайте файл `.env` на основе `.env.example` и заполните его:
```bash
cp .env.example .env
```

3. Настройте файлы данных:
- `data/users.json` - список авторизованных пользователей
- `data/chats.json` - список бесед для отправки отчетов

## Структура проекта

```
Bot-stats/
├── config/          # Конфигурация
│   ├── __init__.py
│   └── settings.py
├── services/        # Сервисы
│   ├── __init__.py
│   ├── bq_client.py          # Работа с BigQuery
│   ├── selenium_collector.py # Сбор отчетов через Selenium
│   ├── status_tracker.py     # Отслеживание статусов
│   ├── report_sender.py      # Отправка отчетов
│   └── scheduler.py          # Планировщик
├── handlers/        # Обработчики команд
│   ├── __init__.py
│   ├── base.py
│   ├── commands.py
│   └── report_handler.py
├── data/            # Данные (создается автоматически)
│   ├── users.json
│   ├── chats.json
│   └── collections_status.json
├── bot.py           # Главный файл запуска
├── requirements.txt
├── .env.example
└── README.md
```

## Команды бота

- `/start` - Начать работу с ботом
- `/help` - Справка по командам
- `/collections` - Показать все коллекции
- `/collections_tsum` - Показать коллекции со статусом "tsum cs"
- `/status <collection_id>` - Показать статус конкретной коллекции

## Настройка пользователей

Файл `data/users.json`:
```json
{
  "users": [
    {
      "telegram_id": 237960664,
      "username": "dasha140501",
      "status": "manager"
    },
    {
      "telegram_id": 313629812,
      "username": "glittersonly",
      "status": "worker"
    }
  ]
}
```

**Важно:** Только пользователи со статусом `"manager"` могут пользоваться ботом. Пользователи со статусом `"worker"` не имеют доступа.

## Настройка бесед

Файл `data/chats.json`:
```json
{
  "chats": [
    {
      "chat_id": "-1001234567890",
      "title": "Название беседы",
      "is_active": true
    }
  ]
}
```

## Запуск

```bash
python bot.py
```

## Автоматическая работа

Бот автоматически:
1. Проверяет статусы коллекций каждые 60 секунд (настраивается через `STATUS_CHECK_INTERVAL`)
2. При изменении статуса на "tsum cs" собирает отчет через Selenium
3. Отправляет отчет во все активные беседы из `data/chats.json`

