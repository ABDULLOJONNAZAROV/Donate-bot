# DONATEX — установка и запуск

## Состав проекта

- `main.py` — Telegram-бот, Mini App API, каталог, заказы и работа с базой данных.
- `donatex_miniapp.html` — интерфейс Telegram Mini App.
- `free-fire-max.png` — изображение для раздела Free Fire.
- `requirements.txt` — Python-зависимости.
- `.env.example` — пример переменных окружения без секретов.

## Требования

- Python 3.10 или новее.
- Telegram Bot Token от @BotFather.
- API-ключ Donatix для каталога и выполнения заказов.
- Для постоянного хранения данных на хостинге рекомендуется PostgreSQL.

## Установка локально

1. Распакуйте архив проекта.
2. Создайте виртуальное окружение:
   ```bash
   python -m venv .venv
   ```
3. Активируйте его и установите зависимости:
   ```bash
   # Windows
   .venv\\Scripts\\activate
   # Linux/macOS
   source .venv/bin/activate

   pip install -r requirements.txt
   ```
4. Скопируйте `.env.example` в `.env` и заполните значения.
5. Запустите бота:
   ```bash
   python main.py
   ```

## Обязательные переменные

- `BOT_TOKEN` — токен Telegram-бота.
- `DONATIX_KEY` — API-ключ Donatix.
- `ADMIN_ID` — Telegram ID главного администратора.

`ADMIN_IDS` — дополнительные администраторы через запятую.
`DATABASE_URL` — PostgreSQL URL. Если не задан, используется `users.json`.
На хостинге с эфемерной файловой системой используйте PostgreSQL, иначе JSON-файл может исчезнуть после redeploy.

## Важная безопасность

- Никогда не публикуйте `.env`, токены, API-ключи или `users.json`.
- Не включайте `DEV_MODE` на публичном сервере. Этот режим предназначен только для локальной разработки и разрешает тестовую авторизацию Mini App без подписи Telegram.
- В Telegram Mini App должен передаваться оригинальный `Telegram.WebApp.initData`; не используйте `initDataUnsafe` как доказательство авторизации.
- Перед реальными платежами проверьте платёжные реквизиты и выполните тестовый заказ на минимальную сумму.
- Перед обновлением сохраните резервную копию базы данных.

## Проверки перед запуском

```bash
python -m py_compile main.py
```

После запуска проверьте `/start`, открытие Mini App, каталог, пополнение, историю и тестовый заказ.
