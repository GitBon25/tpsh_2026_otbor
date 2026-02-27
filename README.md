<h1 align="center">tpsh_2026_otbor</h1>

</h2>

<p align="center">

<img src="https://badges.frapsoft.com/os/v1/open-source.svg?v=103" >

Telegram‑бот, который принимает запрос на русском языке, преобразует его в SQL с помощью GigaChat, выполняет запрос в PostgreSQL и возвращает одно число.

# 📦 Структура проекта
```
.
├── bot/                 # Код Telegram-бота
├── db/                  # SQL-инициализация базы
├── scripts/             # Скрипты (загрузка JSON в БД)
├── data/                # Исходные данные (videos.json)
├── docker-compose.yml   # Конфигурация сервисов
├── Dockerfile           # Образ бота
├── start.sh             # Скрипт для поднятия postgres
└── README.md
```
# ⚙️ Настройка окружения
## 1. Обязательные переменные
Шаблон для подстановки своих переменных находится в файле env_example. Поменяйте в нем нужные переменные, а затем переименуйте в .env, либо создайте новый и скопируйте
### Telegram
```
BOT_TOKEN=your_telegram_bot_token
```
Получить токен можно через @BotFather.

### GigaChat
Необходимо указать:
```
GIGACHAT_CREDENTIALS=base64(client_id:client_secret)
GIGACHAT_SCOPE=ваш_scope(обычно GIGACHAT_API_PERS)
```
Важно:  
- GIGACHAT_CREDENTIALS это base64 от строки CLIENT_ID:CLIENT_SECRET  
- Не вставлять кавычки

Пример генерации base64 (PowerShell):
```
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("CLIENT_ID:CLIENT_SECRET"))
```
!!! CLIENT_ID:CLIENT_SECRET можно получить в личном кабинете по работе с api gigachat) !!!

# 🚀 Запуск проекта
## Сборка и запуск
```
docker compose up --build
```
После запуска:  
- PostgreSQL доступен на localhost:5432  
- Бот начинает polling Telegram

## Остановка
```
docker compose down
```
Полный сброс базы:
```
docker compose down -v
```

Проект разработан для тестового задания ТПШ 2026.
