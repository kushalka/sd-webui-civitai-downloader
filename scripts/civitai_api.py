"""
REST API endpoint for Telegram bot integration
Allows external bots to download models via HTTP requests
"""

import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modules.api.models import *
from modules.api import api
from scripts.civitai_downloader import downloader


class DownloadRequest(BaseModel):
    url: str
    api_key: str = None


class DownloadResponse(BaseModel):
    success: bool
    message: str
    filename: str = None
    path: str = None
    model_name: str = None
    version_name: str = None


def civitai_api(_: gr.Blocks, app):
    """Register API endpoints"""
    
    @app.post("/civitai/download", response_model=DownloadResponse)
    async def download_model(request: DownloadRequest):
        """
        Download a model from Civitai
        
        Parameters:
        - url: Civitai model URL (e.g., https://civitai.com/models/123456)
        - api_key: Optional Civitai API key for early access models
        
        Returns:
        - success: Whether download was successful
        - message: Status message
        - filename: Downloaded file name
        - path: Full path to downloaded file
        - model_name: Model name from Civitai
        - version_name: Version name from Civitai
        """
        try:
            # Set API key
            downloader.api_key = request.api_key.strip() if request.api_key else None
            
            # If no user key, try default key
            if not downloader.api_key:
                default_key = downloader.load_default_api_key()
                if default_key:
                    downloader.api_key = default_key
            
            # Extract model ID
            version_id, error = downloader.extract_model_id(request.url)
            if error:
                raise HTTPException(status_code=400, detail=error)
            
            # Get model info
            model_info, error = downloader.get_model_info(version_id)
            if error:
                raise HTTPException(status_code=400, detail=error)
            
            # Get download URL and filename
            if 'files' not in model_info or len(model_info['files']) == 0:
                raise HTTPException(status_code=404, detail="No files found for download")
            
            file_info = model_info['files'][0]
            download_url = file_info['downloadUrl']
            filename = file_info['name']
            
            # Add API key to download URL if provided
            if downloader.api_key:
                separator = '&' if '?' in download_url else '?'
                download_url = f"{download_url}{separator}token={downloader.api_key}"
            
            # Determine save path
            from modules import shared
            lora_path = os.path.join(
                shared.cmd_opts.lora_dir if hasattr(shared.cmd_opts, 'lora_dir') else 'models/Lora',
                filename
            )
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(lora_path), exist_ok=True)
            
            # Download file
            import requests
            response = requests.get(download_url, stream=True, timeout=120)
            
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Authorization error. Check API key")
            elif response.status_code == 403:
                raise HTTPException(status_code=403, detail="Access forbidden. Model may require API key or subscription")
            elif response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found. Model may have been deleted")
            elif response.status_code == 429:
                raise HTTPException(status_code=429, detail="Download limit exceeded. Try later")
            
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(lora_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            # Verify file was downloaded
            if os.path.exists(lora_path) and os.path.getsize(lora_path) == 0:
                os.remove(lora_path)
                raise HTTPException(status_code=500, detail="Downloaded empty file")
            
            model_name = model_info.get('model', {}).get('name', 'Unknown')
            version_name = model_info.get('name', '')
            
            return DownloadResponse(
                success=True,
                message="Model downloaded successfully",
                filename=filename,
                path=lora_path,
                model_name=model_name,
                version_name=version_name
            )
        
        except requests.exceptions.Timeout:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            raise HTTPException(status_code=504, detail="Timeout. File too large or slow connection")
        except requests.exceptions.ConnectionError:
            if os.path.exists(lora_path):
                os.remove(lora_path)
            raise HTTPException(status_code=503, detail="Connection lost during download")
        except HTTPException:
            raise
        except Exception as e:
            if 'lora_path' in locals() and os.path.exists(lora_path):
                os.remove(lora_path)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
    @app.get("/civitai/status")
    async def get_status():
        """Health check endpoint"""
        return {"status": "online", "service": "civitai-downloader"}


try:
    import gradio as gr
    from modules import script_callbacks
    
    script_callbacks.on_app_started(civitai_api)
    print("[Civitai API] REST API endpoints registered")
except Exception as e:
    print(f"[Civitai API] Failed to register API endpoints: {e}")
