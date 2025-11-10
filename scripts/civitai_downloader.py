import os
import re
import json
import requests
import gradio as gr
from pathlib import Path
from modules import script_callbacks, shared, scripts

class CivitaiDownloader:
    def __init__(self):
        self.api_key = None
        self.config_file = os.path.join(scripts.basedir(), "civitai_api_key.json")
        self.default_key_file = os.path.join(scripts.basedir(), "default_api_key.txt")
        
    def load_api_key(self):
        """Load saved API key from config file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return data.get('api_key', '')
        except Exception as e:
            print(f"Error loading API key: {e}")
        return ''
    
    def load_default_api_key(self):
        """Load default API key from file if exists"""
        try:
            if os.path.exists(self.default_key_file):
                with open(self.default_key_file, 'r') as f:
                    key = f.read().strip()
                    if key:
                        return key
        except Exception as e:
            print(f"Error loading default API key: {e}")
        return None
    
    def save_api_key(self, api_key):
        """Save API key to config file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({'api_key': api_key}, f)
        except Exception as e:
            print(f"Error saving API key: {e}")
        
    def extract_model_id(self, url):
        """Extract model version ID from Civitai URL"""
        # Pattern for model page: https://civitai.com/models/123456
        # Pattern for version: https://civitai.com/models/123456?modelVersionId=789
        
        if not url or not isinstance(url, str):
            return None, "Неверная ссылка"
        
        # Try to extract modelVersionId parameter
        version_match = re.search(r'modelVersionId=(\d+)', url)
        if version_match:
            return version_match.group(1), None
        
        # Try to extract model ID from URL and get latest version
        model_match = re.search(r'civitai\.com/models/(\d+)', url)
        if model_match:
            model_id = model_match.group(1)
            return self.get_latest_version_id(model_id)
        
        return None, "Не удалось извлечь ID модели из ссылки"
    
    def get_latest_version_id(self, model_id):
        """Get the latest version ID for a model"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.get(
                f'https://civitai.com/api/v1/models/{model_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'modelVersions' in data and len(data['modelVersions']) > 0:
                    return str(data['modelVersions'][0]['id']), None
                return None, "Модель не содержит версий для скачивания"
            elif response.status_code == 401:
                return None, "Неверный API ключ. Проверьте ключ или удалите его для публичных моделей"
            elif response.status_code == 403:
                return None, "Доступ запрещён. Возможно, модель приватная и требует API ключ"
            elif response.status_code == 404:
                return None, "Модель не найдена. Проверьте правильность ссылки"
            elif response.status_code == 429:
                return None, "Превышен лимит запросов. Подождите немного и попробуйте снова"
            else:
                return None, f"Ошибка сервера Civitai (код {response.status_code})"
        except requests.exceptions.Timeout:
            return None, "Превышено время ожидания. Проверьте подключение к интернету"
        except requests.exceptions.ConnectionError:
            return None, "Не удалось подключиться к Civitai. Проверьте подключение к интернету"
        except Exception as e:
            return None, f"Ошибка при запросе к API: {str(e)}"
    
    def get_model_info(self, version_id):
        """Get model information from Civitai API"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.get(
                f'https://civitai.com/api/v1/model-versions/{version_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 401:
                return None, "Неверный API ключ. Проверьте ключ или удалите его"
            elif response.status_code == 403:
                return None, "Доступ запрещён. Модель требует API ключ или недоступна"
            elif response.status_code == 404:
                return None, "Версия модели не найдена"
            elif response.status_code == 429:
                return None, "Превышен лимит запросов. Подождите и попробуйте снова"
            else:
                return None, f"Ошибка сервера Civitai (код {response.status_code})"
        except requests.exceptions.Timeout:
            return None, "Превышено время ожидания. Проверьте интернет-соединение"
        except requests.exceptions.ConnectionError:
            return None, "Не удалось подключиться к Civitai. Проверьте интернет"
        except Exception as e:
            return None, f"Ошибка запроса: {str(e)}"
    
    def download_model(self, url, api_key, progress=gr.Progress()):
        """Download LoRA model from Civitai"""
        self.api_key = api_key.strip() if api_key else None
        
        # If no user key, try default key
        if not self.api_key:
            default_key = self.load_default_api_key()
            if default_key:
                self.api_key = default_key
        
        # Auto-save or delete API key
        if self.api_key:
            self.save_api_key(self.api_key)
        else:
            # If key is empty, delete saved key
            if os.path.exists(self.config_file):
                try:
                    os.remove(self.config_file)
                except Exception as e:
                    print(f"Error deleting API key: {e}")
        
        if not url:
            return "❌ Введите ссылку на модель"
        
        progress(0, desc="Извлечение ID модели...")
        version_id, error = self.extract_model_id(url)
        
        if error:
            return f"❌ {error}"
        
        progress(0.2, desc="Получение информации о модели...")
        model_info, error = self.get_model_info(version_id)
        
        if error:
            return f"❌ {error}"
        
        # Get download URL and filename
        if 'files' not in model_info or len(model_info['files']) == 0:
            return "❌ Файлы для скачивания не найдены"
        
        file_info = model_info['files'][0]
        download_url = file_info['downloadUrl']
        filename = file_info['name']
        
        # Add API key to download URL if provided
        if self.api_key:
            separator = '&' if '?' in download_url else '?'
            download_url = f"{download_url}{separator}token={self.api_key}"
        
        # Determine save path
        lora_path = os.path.join(shared.cmd_opts.lora_dir if hasattr(shared.cmd_opts, 'lora_dir') else 'models/Lora', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(lora_path), exist_ok=True)
        
        progress(0.3, desc=f"Скачивание {filename}...")
        
        try:
            response = requests.get(download_url, stream=True, timeout=120)
            
            if response.status_code == 401:
                return "❌ Ошибка авторизации. Проверьте API ключ"
            elif response.status_code == 403:
                return "❌ Доступ запрещён. Возможно, модель требует API ключ или подписку"
            elif response.status_code == 404:
                return "❌ Файл не найден. Возможно, модель была удалена"
            elif response.status_code == 429:
                return "❌ Превышен лимит скачиваний. Попробуйте позже"
            
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(lora_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress_val = 0.3 + (downloaded / total_size) * 0.7
                            progress(progress_val, desc=f"Скачивание: {downloaded / 1024 / 1024:.1f} / {total_size / 1024 / 1024:.1f} MB")
            
            # Verify file was downloaded
            if os.path.exists(lora_path) and os.path.getsize(lora_path) == 0:
                os.remove(lora_path)
                return "❌ Скачан пустой файл. Попробуйте снова"
            
            model_name = model_info.get('model', {}).get('name', 'Unknown')
            version_name = model_info.get('name', '')
            
            return f"✅ Успешно скачано!\n\nМодель: {model_name}\nВерсия: {version_name}\nФайл: {filename}\nПуть: {lora_path}"
        
        except requests.exceptions.Timeout:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            return "❌ Превышено время ожидания. Файл слишком большой или медленное соединение"
        except requests.exceptions.ConnectionError:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            return "❌ Потеряно соединение с интернетом во время скачивания"
        except requests.exceptions.HTTPError as e:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            return f"❌ Ошибка HTTP при скачивании: {e}"
        except OSError as e:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            return f"❌ Ошибка записи файла: {e}. Проверьте права доступа и свободное место"
        except Exception as e:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            return f"❌ Неизвестная ошибка: {str(e)}"

downloader = CivitaiDownloader()

def on_ui_tabs():
    with gr.Blocks(analytics_enabled=False) as civitai_downloader_tab:
        gr.Markdown("# 📥 Civitai LoRA Downloader")
        gr.Markdown("Скачивайте LoRA модели с Civitai по ссылке")
        
        with gr.Row():
            with gr.Column():
                url_input = gr.Textbox(
                    label="Ссылка на модель Civitai",
                    placeholder="https://civitai.com/models/123456 или https://civitai.com/models/123456?modelVersionId=789",
                    lines=1
                )
                
                api_key_input = gr.Textbox(
                    label="API ключ Civitai (автоматически сохраняется)",
                    placeholder="Ваш API ключ",
                    type="password",
                    lines=1,
                    value=downloader.load_api_key()
                )
                
                download_btn = gr.Button("📥 Скачать", variant="primary", size="lg")
                
                output_text = gr.Textbox(
                    label="Статус",
                    lines=10,
                    interactive=False
                )
        
        gr.Markdown("""
        ### Инструкция:
        1. Скопируйте ссылку на LoRA модель с Civitai
        2. Вставьте ссылку в поле выше
        3. (Опционально) Введите ваш API ключ для доступа к ранним релизам
        4. Нажмите "Скачать"
        
        ### Получение API ключа:
        1. Войдите на сайт [Civitai](https://civitai.com)
        2. Перейдите в Settings → API Keys
        3. Создайте новый ключ и скопируйте его
        """)
        
        download_btn.click(
            fn=downloader.download_model,
            inputs=[url_input, api_key_input],
            outputs=[output_text]
        )
    
    return [(civitai_downloader_tab, "Civitai Downloader", "civitai_downloader")]

script_callbacks.on_ui_tabs(on_ui_tabs)
