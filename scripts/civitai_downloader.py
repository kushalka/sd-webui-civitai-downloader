import os
import re
import json
import time
import requests
from pathlib import Path
from modules import shared, scripts

class CivitaiDownloader:
    def __init__(self):
        self.api_key = None
        self.config_file = os.path.join(scripts.basedir(), "civitai_api_key.json")
        self.default_key_file = os.path.join(scripts.basedir(), "default_api_key.txt")
        
        # Create session for connection reuse
        self.session = requests.Session()
        # Set User-Agent to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
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
            
            response = self.session.get(
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
                api_key_info = "\n\n💡 Получить API ключ: https://civitai.com/user/account" if not self.api_key else ""
                return None, f"Неверный API ключ или ключ не предоставлен. Проверьте ключ или получите новый на Civitai.{api_key_info}"
            elif response.status_code == 403:
                if not self.api_key:
                    return None, "❌ Доступ запрещён. Эта модель требует API ключ Civitai.\n\n💡 Решение:\n1. Получите API ключ: https://civitai.com/user/account\n2. Введите ключ в поле 'API ключ' перед скачиванием\n3. Или создайте файл 'default_api_key.txt' с вашим ключом"
                else:
                    return None, "Доступ запрещён. Проверьте правильность API ключа или права доступа к модели"
            elif response.status_code == 404:
                return None, "Модель не найдена. Проверьте правильность ссылки"
            elif response.status_code == 429:
                return None, "Превышен лимит запросов. Подождите немного и попробуйте снова"
            else:
                return None, f"Ошибка сервера Civitai (код {response.status_code})"
        except requests.exceptions.Timeout:
            return None, "Превышено время ожидания. Проверьте подключение к интернету"
        except requests.exceptions.SSLError as e:
            return None, f"Ошибка SSL соединения: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            return None, f"Не удалось подключиться к Civitai. Проверьте подключение к интернету: {str(e)}"
        except requests.exceptions.RequestException as e:
            return None, f"Ошибка запроса к API: {str(e)}"
        except Exception as e:
            return None, f"Неожиданная ошибка при запросе к API: {str(e)}"
    
    def get_model_info(self, version_id):
        """Get model information from Civitai API"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = self.session.get(
                f'https://civitai.com/api/v1/model-versions/{version_id}',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json(), None
            elif response.status_code == 401:
                api_key_info = "\n\n💡 Получить API ключ: https://civitai.com/user/account" if not self.api_key else ""
                return None, f"Неверный API ключ или ключ не предоставлен. Проверьте ключ.{api_key_info}"
            elif response.status_code == 403:
                if not self.api_key:
                    return None, "❌ Доступ запрещён. Эта модель требует API ключ Civitai.\n\n💡 Решение:\n1. Получите API ключ: https://civitai.com/user/account\n2. Введите ключ в поле 'API ключ' перед скачиванием\n3. Или создайте файл 'default_api_key.txt' с вашим ключом"
                else:
                    return None, "Доступ запрещён. Проверьте правильность API ключа или права доступа к модели"
            elif response.status_code == 404:
                return None, "Версия модели не найдена"
            elif response.status_code == 429:
                return None, "Превышен лимит запросов. Подождите и попробуйте снова"
            else:
                return None, f"Ошибка сервера Civitai (код {response.status_code})"
        except requests.exceptions.Timeout:
            return None, "Превышено время ожидания. Проверьте интернет-соединение"
        except requests.exceptions.SSLError as e:
            return None, f"Ошибка SSL соединения: {str(e)}"
        except requests.exceptions.ConnectionError as e:
            return None, f"Не удалось подключиться к Civitai. Проверьте интернет: {str(e)}"
        except requests.exceptions.RequestException as e:
            return None, f"Ошибка запроса к API: {str(e)}"
        except Exception as e:
            return None, f"Неожиданная ошибка при запросе: {str(e)}"
    
    def download_model(self, url, api_key, progress=None):
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
        
        if progress:
            progress(0, desc="Извлечение ID модели...")
        version_id, error = self.extract_model_id(url)
        
        if error:
            return f"❌ {error}"
        
        if progress:
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
        
        if progress:
            progress(0.3, desc=f"Скачивание {filename}...")
        
        # Download with retry mechanism
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    if progress:
                        progress(0.3, desc=f"Повторная попытка {attempt + 1}/{max_retries}...")
                    time.sleep(retry_delay * attempt)  # Exponential backoff
                    # Clean up partial file before retry
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                
                response = self.session.get(download_url, stream=True, timeout=300)
                
                if response.status_code == 401:
                    if not self.api_key:
                        return "❌ Ошибка авторизации. Модель требует API ключ.\n\n💡 Получите ключ: https://civitai.com/user/account\nЗатем введите его в поле 'API ключ'"
                    else:
                        return "❌ Ошибка авторизации. Проверьте правильность API ключа или получите новый: https://civitai.com/user/account"
                elif response.status_code == 403:
                    if not self.api_key:
                        return "❌ Доступ запрещён. Эта модель требует API ключ Civitai.\n\n💡 Решение:\n1. Получите API ключ: https://civitai.com/user/account\n2. Введите ключ в поле 'API ключ' перед скачиванием\n3. Или создайте файл 'default_api_key.txt' с вашим ключом"
                    else:
                        return "❌ Доступ запрещён. Проверьте правильность API ключа или права доступа к модели"
                elif response.status_code == 404:
                    return "❌ Файл не найден. Возможно, модель была удалена"
                elif response.status_code == 429:
                    return "❌ Превышен лимит скачиваний. Попробуйте позже"
                
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                try:
                    with open(lora_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0 and progress:
                                    progress_val = 0.3 + (downloaded / total_size) * 0.7
                                    progress(progress_val, desc=f"Скачивание: {downloaded / 1024 / 1024:.1f} / {total_size / 1024 / 1024:.1f} MB")
                    
                    # Verify file was downloaded correctly
                    if not os.path.exists(lora_path):
                        raise Exception("Файл не был создан")
                    
                    file_size = os.path.getsize(lora_path)
                    if file_size == 0:
                        if os.path.exists(lora_path):
                            os.remove(lora_path)
                        raise Exception("Скачан пустой файл")
                    
                    # Verify file size matches expected size (if content-length was provided)
                    if total_size > 0 and file_size != total_size:
                        if os.path.exists(lora_path):
                            os.remove(lora_path)
                        raise Exception(f"Размер файла не совпадает: получено {file_size}, ожидалось {total_size}")
                    
                    # Success - break out of retry loop
                    break
                    
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ChunkedEncodingError) as e:
                    # Connection errors during download - retry if attempts left
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    if attempt < max_retries - 1:
                        continue  # Retry
                    else:
                        raise  # Last attempt failed, re-raise
                except OSError as e:
                    # File system errors - don't retry
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    raise
                
            except requests.exceptions.Timeout:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                if attempt < max_retries - 1:
                    continue  # Retry
                return "❌ Превышено время ожидания. Файл слишком большой или медленное соединение"
            
            except requests.exceptions.SSLError as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                return f"❌ Ошибка SSL соединения: {str(e)}"
            
            except requests.exceptions.ConnectionError as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                if attempt < max_retries - 1:
                    continue  # Retry
                return f"❌ Потеряно соединение с интернетом во время скачивания: {str(e)}"
            
            except requests.exceptions.HTTPError as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                return f"❌ Ошибка HTTP при скачивании: {e}"
            
            except requests.exceptions.RequestException as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                if attempt < max_retries - 1:
                    continue  # Retry
                return f"❌ Ошибка сетевого запроса: {str(e)}"
            
            except OSError as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                return f"❌ Ошибка записи файла: {e}. Проверьте права доступа и свободное место"
            
            except Exception as e:
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                if attempt < max_retries - 1 and "размер файла" not in str(e).lower() and "пустой файл" not in str(e).lower():
                    continue  # Retry for certain errors
                return f"❌ Ошибка при скачивании: {str(e)}"
        else:
            # All retries exhausted
            if os.path.exists(lora_path):
                try:
                    os.remove(lora_path)
                except:
                    pass
            return "❌ Не удалось скачать файл после нескольких попыток"
        
        # Success
        model_name = model_info.get('model', {}).get('name', 'Unknown')
        version_name = model_info.get('name', '')
        
        return f"✅ Успешно скачано!\n\nМодель: {model_name}\nВерсия: {version_name}\nФайл: {filename}\nПуть: {lora_path}"

# Create a single global instance
downloader = CivitaiDownloader()
