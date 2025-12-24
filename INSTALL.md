# Инструкция по установке и запуску

## Шаг 1: Установка зависимостей

```bash
cd Bot-stats
pip install -r requirements.txt
```

## Шаг 2: Настройка переменных окружения

Создайте файл `.env` в корне проекта `Bot-stats/`:

```bash
cp .env.example .env
```

Заполните файл `.env`:

```env
# Telegram Bot
TELEGRAM_TOKEN=ваш_токен_бота
TELEGRAM_BOT_USERNAME=showoff_bot

# BigQuery
BIGQUERY_PROJECT_ID=looky-374212
BIGQUERY_TABLE_COLLECTIONS=looky-374212.mosaica.showoff_custom_collections
BIGQUERY_TABLE_ITEMS=looky-374212.mosaica.showoff_custom_collections_items
BIGQUERY_TABLE_ACTIONS=looky-374212.mosaica.showoff_operators_actions

# Google Application Credentials (JSON строка)
GOOGLE_APPLICATION_CREDENTIALS={"type": "service_account", "project_id": "...", ...}

# DressCode Admin credentials
ADMIN_EMAIL=ваш_email@example.com
ADMIN_PASSWORD=ваш_пароль

# Интервал проверки статусов (в секундах)
STATUS_CHECK_INTERVAL=60
```

**Важно:** `GOOGLE_APPLICATION_CREDENTIALS` должен быть JSON строкой в одну строку. Если у вас есть файл с ключом, преобразуйте его:

```bash
# Linux/Mac
cat credentials.json | jq -c

# Windows PowerShell
Get-Content credentials.json | ConvertFrom-Json | ConvertTo-Json -Compress
```

## Шаг 3: Настройка пользователей

Создайте файл `data/users.json`:

```bash
cp data/users.json.example data/users.json
```

Отредактируйте `data/users.json` и добавьте пользователей:

```json
{
  "users": [
    {
      "telegram_id": 237960664,
      "username": "dasha140501",
      "status": "manager"
    }
  ]
}
```

**Важно:** 
- Только пользователи со статусом `"manager"` могут пользоваться ботом
- Пользователи со статусом `"worker"` не имеют доступа
- Чтобы узнать свой ID в Telegram, напишите боту [@userinfobot](https://t.me/userinfobot)

## Шаг 4: Настройка бесед

Создайте файл `data/chats.json`:

```bash
cp data/chats.json.example data/chats.json
```

Отредактируйте `data/chats.json` и добавьте ID бесед, куда будут отправляться отчеты:

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

Чтобы узнать ID беседы:
1. Добавьте бота [@userinfobot](https://t.me/userinfobot) в беседу
2. Напишите `/start` в беседе
3. Бот покажет ID беседы (начинается с `-`)

## Шаг 5: Запуск бота

```bash
python bot.py
```

Бот начнет работать и автоматически:
- Проверять статусы коллекций каждые 60 секунд
- При изменении статуса на "tsum cs" собирать отчет через Selenium
- Отправлять отчеты во все активные беседы

## Команды бота

- `/start` - Начать работу с ботом
- `/help` - Справка по командам
- `/collections` - Показать все коллекции
- `/collections_tsum` - Показать коллекции со статусом "tsum cs"
- `/status <collection_id>` - Показать статус конкретной коллекции

## Устранение проблем

### Ошибка "Не задан TELEGRAM_TOKEN"
Проверьте, что файл `.env` существует и содержит `TELEGRAM_TOKEN`.

### Ошибка "Failed to initialize BigQuery client"
Проверьте, что `GOOGLE_APPLICATION_CREDENTIALS` содержит валидный JSON ключ сервисного аккаунта.

### Ошибка "Login failed" в Selenium
Проверьте, что `ADMIN_EMAIL` и `ADMIN_PASSWORD` правильные.

### Бот не отвечает
Проверьте, что:
1. Ваш `telegram_id` добавлен в `data/users.json`
2. Ваш статус установлен как `"manager"` (не `"worker"`)

## Логи

Логи сохраняются в файл `logs/bot.log`.

