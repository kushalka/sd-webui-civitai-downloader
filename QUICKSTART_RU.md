# Быстрый старт - Интеграция с Telegram ботом

## Что это даёт?

Ваш Telegram бот сможет:
- ✅ Скачивать модели с Civitai на все ваши PC с SD WebUI
- ✅ Проверять статус серверов (онлайн/оффлайн)
- ✅ Управлять скачиванием удалённо

## Шаг 1: Настройка расширения

1. Убедитесь, что расширение установлено в папку `extensions` вашего SD WebUI

2. Запустите WebUI с API и сетевым доступом:
   ```bash
   python webui.py --api --listen
   ```
   
   - `--api` - включает REST API
   - `--listen` - разрешает подключения из сети

## Шаг 2: Проверка работы API

Откройте браузер или выполните в терминале:

```bash
curl http://localhost:7860/civitai/status
```

Должен вернуться ответ:
```json
{"status": "online", "service": "civitai-downloader"}
```

✅ Если видите этот ответ - API работает!

## Шаг 3: Найти IP адреса ваших PC

### Windows:
```cmd
ipconfig
```
Ищите строку: `IPv4 Address. . . . . . . . . . . : 192.168.X.X`

### Linux/Mac:
```bash
ifconfig
```
или
```bash
ip addr
```

Запишите IP адреса всех ваших PC с SD WebUI.

## Шаг 4: Код для Telegram бота

### Вариант 1: Простой пример (копируй-вставляй)

```python
import requests

# Список ваших серверов
SERVERS = [
    {"name": "PC1", "url": "http://192.168.1.100:7860"},
    {"name": "PC2", "url": "http://192.168.1.101:7860"},
]

def download_model(server_url, civitai_url, api_key=None):
    """Скачать модель на сервер"""
    try:
        response = requests.post(
            f"{server_url}/civitai/download",
            json={
                "url": civitai_url,
                "api_key": api_key  # None если не нужен
            },
            timeout=300  # 5 минут
        )
        
        if response.status_code == 200:
            result = response.json()
            return f"✅ Скачано: {result['filename']}"
        else:
            return f"❌ Ошибка: {response.text}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

# Использование
result = download_model(
    server_url="http://192.168.1.100:7860",
    civitai_url="https://civitai.com/models/123456"
)
print(result)
```

### Вариант 2: Полноценный бот (aiogram 3.x)

```python
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
import requests
import asyncio

bot = Bot(token="YOUR_BOT_TOKEN")
dp = Dispatcher()

SERVERS = [
    {"name": "PC1", "url": "http://192.168.1.100:7860"},
    {"name": "PC2", "url": "http://192.168.1.101:7860"},
]

@dp.message(Command("download"))
async def download_command(message: types.Message):
    """Команда: /download https://civitai.com/models/123456"""
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: /download <ссылка_на_Civitai>")
        return
    
    civitai_url = args[1]
    await message.reply("⏳ Начинаю скачивание на все серверы...")
    
    for server in SERVERS:
        try:
            response = requests.post(
                f"{server['url']}/civitai/download",
                json={"url": civitai_url},
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                await message.reply(
                    f"✅ {server['name']}\n"
                    f"📦 {result['filename']}\n"
                    f"📁 {result['model_name']}"
                )
            else:
                await message.reply(f"❌ {server['name']}: Ошибка {response.status_code}")
        
        except Exception as e:
            await message.reply(f"❌ {server['name']}: {str(e)}")

@dp.message(Command("servers"))
async def servers_command(message: types.Message):
    """Проверить статус всех серверов"""
    status_lines = ["🖥 Статус серверов:\n"]
    
    for server in SERVERS:
        try:
            response = requests.get(f"{server['url']}/civitai/status", timeout=5)
            if response.status_code == 200:
                status = "🟢 Онлайн"
            else:
                status = "🔴 Оффлайн"
        except:
            status = "🔴 Недоступен"
        
        status_lines.append(f"{status} {server['name']}")
    
    await message.reply("\n".join(status_lines))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

### Вариант 3: Бот с классом (рекомендуется)

Скопируйте класс `CivitaiDownloaderClient` из файла `telegram_bot_example.py` в ваш проект и используйте:

```python
from civitai_client import CivitaiDownloaderClient

client = CivitaiDownloaderClient([
    {"name": "PC1", "url": "http://192.168.1.100:7860"},
    {"name": "PC2", "url": "http://192.168.1.101:7860"},
])

# Скачивание на все серверы
results = client.download_to_all_servers(
    civitai_url="https://civitai.com/models/123456",
    api_key="your_civitai_api_key"  # Опционально
)

for server_name, result in results.items():
    if result["success"]:
        print(f"✅ {server_name}: {result['filename']}")
    else:
        print(f"❌ {server_name}: {result['message']}")
```

## Шаг 5: Тестирование

1. Запустите вашего бота
2. Отправьте команду: `/servers`
3. Убедитесь, что серверы онлайн
4. Попробуйте скачать модель: `/download https://civitai.com/models/123456`

## Частые вопросы

### Бот не видит серверы

1. Проверьте, что WebUI запущен с флагами `--api --listen`
2. Убедитесь, что IP адреса правильные
3. Проверьте файрвол Windows/Linux

### "Connection refused"

- Используйте `--listen` при запуске WebUI
- Проверьте порт 7860 (должен быть открыт)

### Безопасность

⚠️ **ВАЖНО:** Не открывайте порт 7860 в интернет без защиты!

Варианты защиты:
1. **VPN** (Tailscale, WireGuard) - рекомендуется
2. **Ngrok** - для тестирования
3. **Firewall** - разрешить только определённые IP

## Дополнительные возможности

### Скачивание с API ключом Civitai

```python
result = client.download_model(
    server_url="http://192.168.1.100:7860",
    civitai_url="https://civitai.com/models/123456",
    api_key="ваш_ключ_civitai"  # Для приватных моделей
)
```

### Проверка статуса сервера

```python
is_online = client.check_server_status("http://192.168.1.100:7860")
print("Сервер", "онлайн" if is_online else "оффлайн")
```

### Получить список доступных серверов

```python
available = client.get_available_servers()
print(f"Доступно серверов: {len(available)}")
```

## API Endpoints

### GET `/civitai/status`
Проверка работы сервиса

### POST `/civitai/download`
Скачивание модели

Параметры:
```json
{
  "url": "https://civitai.com/models/123456",
  "api_key": "optional_civitai_key"
}
```

Ответ:
```json
{
  "success": true,
  "message": "Model downloaded successfully",
  "filename": "model.safetensors",
  "path": "C:/sd-webui/models/Lora/model.safetensors",
  "model_name": "Amazing LoRA",
  "version_name": "v1.0"
}
```

## Куда дальше?

- 📚 Полная документация: [API_INTEGRATION.md](API_INTEGRATION.md)
- 💻 Примеры кода: [telegram_bot_example.py](telegram_bot_example.py)
- 📖 Основной README: [README.md](README.md)

## Помощь

Если что-то не работает:
1. Проверьте логи SD WebUI в консоли
2. Убедитесь, что видите сообщение: `[Civitai API] REST API endpoints registered`
3. Попробуйте API вручную через `curl` или браузер
4. Проверьте сетевые настройки (IP, порты, файрвол)

Успехов! 🚀
