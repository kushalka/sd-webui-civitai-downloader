"""
Пример интеграции Telegram бота с расширением Civitai Downloader

Этот файл показывает, как ваш Telegram бот может взаимодействовать 
с расширением для скачивания моделей на удалённые PC с SD WebUI
"""

import requests
import json
import os
from typing import List, Dict, Optional


class CivitaiDownloaderClient:
    """Клиент для работы с API Civitai Downloader"""
    
    def __init__(self, servers: List[Dict[str, str]]):
        """
        Инициализация клиента
        
        Args:
            servers: Список серверов в формате:
                [
                    {"name": "PC1", "url": "http://192.168.1.100:7860"},
                    {"name": "PC2", "url": "http://192.168.1.101:7860"},
                ]
        """
        self.servers = servers
    
    def check_server_status(self, server_url: str) -> bool:
        """Проверка доступности сервера"""
        try:
            response = requests.get(
                f"{server_url}/civitai/status",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Server {server_url} is offline: {e}")
            return False
    
    def download_model(
        self, 
        server_url: str, 
        civitai_url: str, 
        api_key: Optional[str] = None
    ) -> Dict:
        """
        Скачивание модели на указанный сервер
        
        Args:
            server_url: URL сервера SD WebUI (например, http://192.168.1.100:7860)
            civitai_url: Ссылка на модель Civitai
            api_key: API ключ Civitai (опционально)
        
        Returns:
            Словарь с результатом:
            {
                "success": True/False,
                "message": "...",
                "filename": "...",
                "path": "...",
                "model_name": "...",
                "version_name": "..."
            }
        """
        try:
            payload = {
                "url": civitai_url,
                "api_key": api_key
            }
            
            response = requests.post(
                f"{server_url}/civitai/download",
                json=payload,
                timeout=300  # 5 минут на скачивание
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "message": f"Error {response.status_code}: {response.text}"
                }
        
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Timeout: скачивание заняло слишком много времени"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка: {str(e)}"
            }
    
    def download_to_all_servers(
        self, 
        civitai_url: str, 
        api_key: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Скачивание модели на все доступные серверы
        
        Returns:
            Словарь с результатами для каждого сервера:
            {
                "PC1": {"success": True, ...},
                "PC2": {"success": False, ...}
            }
        """
        results = {}
        
        for server in self.servers:
            server_name = server["name"]
            server_url = server["url"]
            
            # Проверка доступности
            if not self.check_server_status(server_url):
                results[server_name] = {
                    "success": False,
                    "message": "Сервер недоступен"
                }
                continue
            
            # Скачивание
            result = self.download_model(server_url, civitai_url, api_key)
            results[server_name] = result
        
        return results
    
    def get_available_servers(self) -> List[str]:
        """Получение списка доступных серверов"""
        available = []
        for server in self.servers:
            if self.check_server_status(server["url"]):
                available.append(server["name"])
        return available
    
    def upload_file(
        self,
        server_url: str,
        file_path: str,
        custom_filename: Optional[str] = None
    ) -> Dict:
        """
        Загрузка safetensors файла на указанный сервер
        
        Args:
            server_url: URL сервера SD WebUI (например, http://192.168.1.100:7860)
            file_path: Путь к safetensors файлу на локальной машине
            custom_filename: Опциональное имя файла (если не указано, используется оригинальное имя)
        
        Returns:
            Словарь с результатом:
            {
                "success": True/False,
                "message": "...",
                "filename": "...",
                "path": "..."
            }
        """
        try:
            # Проверка существования файла
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "message": f"Файл не найден: {file_path}"
                }
            
            # Проверка расширения файла
            if not file_path.lower().endswith('.safetensors'):
                return {
                    "success": False,
                    "message": "Поддерживаются только файлы формата .safetensors"
                }
            
            # Подготовка данных для отправки
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                data = {}
                if custom_filename:
                    data['filename'] = custom_filename
                
                response = requests.post(
                    f"{server_url}/civitai/upload",
                    files=files,
                    data=data,
                    timeout=300  # 5 минут на загрузку
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "message": f"Error {response.status_code}: {response.text}"
                }
        
        except FileNotFoundError:
            return {
                "success": False,
                "message": f"Файл не найден: {file_path}"
            }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Timeout: загрузка заняла слишком много времени"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка: {str(e)}"
            }
    
    def upload_to_all_servers(
        self,
        file_path: str,
        custom_filename: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Загрузка safetensors файла на все доступные серверы
        
        Args:
            file_path: Путь к safetensors файлу на локальной машине
            custom_filename: Опциональное имя файла
        
        Returns:
            Словарь с результатами для каждого сервера:
            {
                "PC1": {"success": True, ...},
                "PC2": {"success": False, ...}
            }
        """
        results = {}
        
        for server in self.servers:
            server_name = server["name"]
            server_url = server["url"]
            
            # Проверка доступности
            if not self.check_server_status(server_url):
                results[server_name] = {
                    "success": False,
                    "message": "Сервер недоступен"
                }
                continue
            
            # Загрузка
            result = self.upload_file(server_url, file_path, custom_filename)
            results[server_name] = result
        
        return results


# ============================================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ В TELEGRAM БОТЕ
# ============================================================================

def example_telegram_bot():
    """Пример интеграции с Telegram ботом (aiogram/python-telegram-bot)"""
    
    # Инициализация клиента
    client = CivitaiDownloaderClient([
        {"name": "Рабочий ПК", "url": "http://192.168.1.100:7860"},
        {"name": "Домашний ПК", "url": "http://192.168.1.101:7860"},
        {"name": "VPS Сервер", "url": "http://10.0.0.5:7860"},
    ])
    
    # ===== Пример 1: Проверка доступных серверов =====
    available = client.get_available_servers()
    print(f"Доступные серверы: {', '.join(available)}")
    
    # ===== Пример 2: Скачивание на один сервер =====
    civitai_url = "https://civitai.com/models/123456"
    api_key = "your_civitai_api_key"  # Опционально
    
    result = client.download_model(
        server_url="http://192.168.1.100:7860",
        civitai_url=civitai_url,
        api_key=api_key
    )
    
    if result["success"]:
        print(f"✅ Модель скачана: {result['filename']}")
        print(f"Путь: {result['path']}")
        print(f"Модель: {result['model_name']} ({result['version_name']})")
    else:
        print(f"❌ Ошибка: {result['message']}")
    
    # ===== Пример 3: Скачивание на все серверы =====
    results = client.download_to_all_servers(civitai_url, api_key)
    
    for server_name, result in results.items():
        if result["success"]:
            print(f"✅ {server_name}: {result['filename']}")
        else:
            print(f"❌ {server_name}: {result['message']}")
    
    # ===== Пример 4: Загрузка safetensors файла =====
    safetensors_file = "model.safetensors"  # Путь к файлу на локальной машине
    result = client.upload_file(
        server_url="http://192.168.1.100:7860",
        file_path=safetensors_file,
        custom_filename="my_model.safetensors"  # Опционально
    )
    
    if result["success"]:
        print(f"✅ Файл загружен: {result['filename']}")
        print(f"Путь: {result['path']}")
    else:
        print(f"❌ Ошибка: {result['message']}")
    
    # ===== Пример 5: Загрузка на все серверы =====
    results = client.upload_to_all_servers(safetensors_file)
    
    for server_name, result in results.items():
        if result["success"]:
            print(f"✅ {server_name}: {result['filename']}")
        else:
            print(f"❌ {server_name}: {result['message']}")


# ============================================================================
# ПРИМЕР С AIOGRAM (современная библиотека для Telegram ботов)
# ============================================================================

"""
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

bot = Bot(token="YOUR_BOT_TOKEN")
dp = Dispatcher()

# Инициализация клиента
client = CivitaiDownloaderClient([
    {"name": "PC1", "url": "http://192.168.1.100:7860"},
    {"name": "PC2", "url": "http://192.168.1.101:7860"},
])

@dp.message(Command("download"))
async def download_command(message: types.Message):
    # Получаем ссылку из команды
    # Формат: /download https://civitai.com/models/123456
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: /download <ссылка_civitai>")
        return
    
    civitai_url = args[1]
    
    # Показываем доступные серверы
    available = client.get_available_servers()
    if not available:
        await message.reply("❌ Нет доступных серверов")
        return
    
    await message.reply(f"⏳ Скачиваю на {len(available)} серверов...")
    
    # Скачиваем на все серверы
    results = client.download_to_all_servers(civitai_url)
    
    # Формируем ответ
    response_lines = ["📊 Результаты скачивания:\n"]
    for server_name, result in results.items():
        if result["success"]:
            response_lines.append(
                f"✅ {server_name}:\n"
                f"  📦 {result['filename']}\n"
                f"  📁 {result['model_name']}"
            )
        else:
            response_lines.append(
                f"❌ {server_name}: {result['message']}"
            )
    
    await message.reply("\n\n".join(response_lines))

@dp.message(Command("servers"))
async def servers_command(message: types.Message):
    # Показываем статус всех серверов
    status_lines = ["🖥 Статус серверов:\n"]
    
    for server in client.servers:
        is_online = client.check_server_status(server["url"])
        status = "🟢 Онлайн" if is_online else "🔴 Оффлайн"
        status_lines.append(f"{status} {server['name']}")
    
    await message.reply("\n".join(status_lines))

@dp.message(lambda m: m.document and m.document.file_name.endswith('.safetensors'))
async def handle_safetensors_file(message: types.Message):
    """Обработка safetensors файла, отправленного в Telegram"""
    try:
        # Скачиваем файл из Telegram
        file_info = await bot.get_file(message.document.file_id)
        file_path = f"/tmp/{message.document.file_name}"
        
        await bot.download_file(file_info.file_path, file_path)
        
        await message.reply("⏳ Загружаю файл на серверы...")
        
        # Загружаем на все серверы
        results = client.upload_to_all_servers(file_path)
        
        # Формируем ответ
        response_lines = ["📊 Результаты загрузки:\n"]
        for server_name, result in results.items():
            if result["success"]:
                response_lines.append(
                    f"✅ {server_name}:\n"
                    f"  📦 {result['filename']}\n"
                    f"  📁 {result['path']}"
                )
            else:
                response_lines.append(
                    f"❌ {server_name}: {result['message']}"
                )
        
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
        
        await message.reply("\n\n".join(response_lines))
    
    except Exception as e:
        await message.reply(f"❌ Ошибка при обработке файла: {str(e)}")

# Запуск бота
if __name__ == "__main__":
    dp.run_polling(bot)
"""


# ============================================================================
# ПРИМЕР С PYTHON-TELEGRAM-BOT (старая библиотека)
# ============================================================================

"""
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

client = CivitaiDownloaderClient([
    {"name": "PC1", "url": "http://192.168.1.100:7860"},
])

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Использование: /download <ссылка>")
        return
    
    civitai_url = context.args[0]
    await update.message.reply_text("⏳ Скачиваю...")
    
    results = client.download_to_all_servers(civitai_url)
    
    for server_name, result in results.items():
        if result["success"]:
            await update.message.reply_text(
                f"✅ {server_name}: {result['filename']}"
            )
        else:
            await update.message.reply_text(
                f"❌ {server_name}: {result['message']}"
            )

def main():
    app = Application.builder().token("YOUR_BOT_TOKEN").build()
    app.add_handler(CommandHandler("download", download))
    app.run_polling()

if __name__ == "__main__":
    main()
"""


if __name__ == "__main__":
    # Запуск примера
    example_telegram_bot()
