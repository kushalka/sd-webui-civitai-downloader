# API интеграция для Telegram бота

## Описание

Это расширение теперь предоставляет REST API для удалённого скачивания моделей с Civitai. Ваш Telegram бот может обращаться к этому API и скачивать модели на все ваши PC с установленным Stable Diffusion WebUI.

## Активация API

1. Убедитесь, что WebUI запущен с параметром `--api`:
   ```bash
   python webui.py --api
   ```

2. Расширение автоматически зарегистрирует API эндпоинты при запуске WebUI

3. Проверьте доступность API:
   ```bash
   curl http://localhost:7860/civitai/status
   ```
   
   Ответ должен быть:
   ```json
   {"status": "online", "service": "civitai-downloader"}
   ```

## API Endpoints

### 1. Проверка статуса (Health Check)

**GET** `/civitai/status`

Проверяет, работает ли сервис.

**Пример запроса:**
```bash
curl http://localhost:7860/civitai/status
```

**Ответ:**
```json
{
  "status": "online",
  "service": "civitai-downloader"
}
```

---

### 2. Скачивание модели

**POST** `/civitai/download`

Скачивает модель с Civitai на сервер.

**Параметры (JSON):**
- `url` (обязательный): Ссылка на модель Civitai
- `api_key` (опциональный): API ключ Civitai для приватных моделей

**Пример запроса (curl):**
```bash
curl -X POST http://localhost:7860/civitai/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://civitai.com/models/123456",
    "api_key": "your_api_key_here"
  }'
```

**Пример запроса (Python):**
```python
import requests

response = requests.post(
    "http://localhost:7860/civitai/download",
    json={
        "url": "https://civitai.com/models/123456",
        "api_key": "your_api_key"  # Опционально
    }
)

result = response.json()
print(result)
```

**Успешный ответ (200):**
```json
{
  "success": true,
  "message": "Model downloaded successfully",
  "filename": "model_name_v1.safetensors",
  "path": "C:/stable-diffusion-webui/models/Lora/model_name_v1.safetensors",
  "model_name": "Amazing LoRA",
  "version_name": "v1.0"
}
```

**Ошибки:**
- `400 Bad Request` - Неверная ссылка или недоступная модель
- `401 Unauthorized` - Неверный API ключ
- `403 Forbidden` - Модель требует подписку или API ключ
- `404 Not Found` - Модель или файл не найден
- `429 Too Many Requests` - Превышен лимит скачиваний
- `500 Internal Server Error` - Внутренняя ошибка сервера
- `503 Service Unavailable` - Нет соединения с Civitai
- `504 Gateway Timeout` - Превышено время скачивания

## Интеграция с Telegram ботом

### Быстрый старт

1. Скопируйте класс `CivitaiDownloaderClient` из файла `telegram_bot_example.py`

2. Инициализируйте клиент с вашими серверами:
   ```python
   from civitai_client import CivitaiDownloaderClient
   
   client = CivitaiDownloaderClient([
       {"name": "PC1", "url": "http://192.168.1.100:7860"},
       {"name": "PC2", "url": "http://192.168.1.101:7860"},
   ])
   ```

3. Используйте в вашем боте:
   ```python
   # Скачивание на один сервер
   result = client.download_model(
       server_url="http://192.168.1.100:7860",
       civitai_url="https://civitai.com/models/123456",
       api_key="your_api_key"  # Опционально
   )
   
   # Скачивание на все доступные серверы
   results = client.download_to_all_servers(
       civitai_url="https://civitai.com/models/123456",
       api_key="your_api_key"  # Опционально
   )
   ```

### Полные примеры

В файле `telegram_bot_example.py` вы найдёте:
- ✅ Готовый класс-клиент для работы с API
- ✅ Пример бота на `aiogram` (современная библиотека)
- ✅ Пример бота на `python-telegram-bot` (старая библиотека)
- ✅ Обработка ошибок и статусов серверов

## Настройка доступа

### Локальная сеть

Если все ваши PC в одной локальной сети:

1. Запустите WebUI с параметром `--listen`:
   ```bash
   python webui.py --api --listen
   ```

2. Узнайте IP адрес компьютера:
   - Windows: `ipconfig`
   - Linux/Mac: `ifconfig`

3. Используйте этот IP в Telegram боте:
   ```python
   client = CivitaiDownloaderClient([
       {"name": "PC1", "url": "http://192.168.1.100:7860"},
   ])
   ```

### Удалённый доступ (через интернет)

Если вы хотите управлять серверами из интернета:

#### Вариант 1: Reverse Proxy (ngrok)

1. Установите [ngrok](https://ngrok.com/):
   ```bash
   ngrok http 7860
   ```

2. Используйте полученный URL:
   ```python
   client = CivitaiDownloaderClient([
       {"name": "PC1", "url": "https://abc123.ngrok.io"},
   ])
   ```

#### Вариант 2: VPN (WireGuard/Tailscale)

1. Настройте VPN между серверами и ботом
2. Используйте внутренние IP адреса VPN

#### Вариант 3: Проброс портов (Port Forwarding)

1. Настройте проброс порта 7860 на роутере
2. Используйте внешний IP или домен

**⚠️ БЕЗОПАСНОСТЬ:**
- Не открывайте API в интернет без авторизации
- Используйте VPN или reverse proxy с аутентификацией
- Рассмотрите добавление токена авторизации в API

## Безопасность

### Добавление базовой аутентификации

Вы можете добавить простую проверку токена в `civitai_api.py`:

```python
from fastapi import Header, HTTPException

async def verify_token(x_token: str = Header()):
    if x_token != "your_secret_token":
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/civitai/download", dependencies=[Depends(verify_token)])
async def download_model(request: DownloadRequest):
    # ... существующий код
```

Использование в боте:
```python
headers = {"X-Token": "your_secret_token"}
response = requests.post(url, json=payload, headers=headers)
```

### Рекомендации

1. **Используйте HTTPS** для продакшна
2. **Ограничьте доступ** по IP адресам
3. **Мониторьте логи** для обнаружения подозрительной активности
4. **Регулярно обновляйте** пароли и токены

## Тестирование

### Проверка API вручную

1. Проверка статуса:
   ```bash
   curl http://localhost:7860/civitai/status
   ```

2. Тестовое скачивание:
   ```bash
   curl -X POST http://localhost:7860/civitai/download \
     -H "Content-Type: application/json" \
     -d '{"url": "https://civitai.com/models/123456"}'
   ```

3. Проверка в браузере:
   - Откройте `http://localhost:7860/docs`
   - Там вы увидите Swagger UI с документацией API

### Python тест

```python
import requests

# Проверка доступности
status = requests.get("http://localhost:7860/civitai/status").json()
print(f"Status: {status}")

# Тестовое скачивание
result = requests.post(
    "http://localhost:7860/civitai/download",
    json={"url": "https://civitai.com/models/123456"}
).json()

if result["success"]:
    print(f"✅ Downloaded: {result['filename']}")
else:
    print(f"❌ Error: {result['message']}")
```

## Устранение проблем

### API не отвечает

1. Проверьте, что WebUI запущен с флагом `--api`
2. Убедитесь, что порт 7860 не занят
3. Проверьте файрвол и антивирус

### Ошибка "Connection refused"

1. Используйте `--listen` для доступа извне
2. Проверьте IP адрес сервера
3. Убедитесь, что порт открыт

### Модель не скачивается

1. Проверьте правильность ссылки Civitai
2. Попробуйте скачать через веб-интерфейс расширения
3. Проверьте логи WebUI на наличие ошибок

### Медленное скачивание

1. Увеличьте timeout в клиенте (по умолчанию 300 секунд)
2. Проверьте скорость интернета
3. Попробуйте скачать файл напрямую с Civitai

## Дополнительные возможности

### Мониторинг скачивания

Добавьте webhook для уведомлений о завершении:

```python
# В civitai_api.py
@app.post("/civitai/webhook/set")
async def set_webhook(webhook_url: str):
    # Сохранить webhook URL
    # Отправлять уведомление при завершении скачивания
    pass
```

### Очередь скачиваний

Для больших моделей можно добавить фоновую очередь:

```python
from celery import Celery

app = Celery('tasks', broker='redis://localhost:6379')

@app.task
def download_model_task(url, api_key):
    # Скачивание в фоне
    pass
```

## Поддержка

Если у вас возникли вопросы или проблемы:
1. Проверьте логи WebUI
2. Посмотрите примеры в `telegram_bot_example.py`
3. Создайте issue в репозитории

## Лицензия

MIT License - используйте свободно в своих проектах
