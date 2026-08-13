"""
REST API endpoint for Telegram bot integration
Allows external bots to download models via HTTP requests
"""

import os
import json
import sys
import time
from typing import Optional, List
from pathlib import Path
import gradio as gr
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from modules.api.models import *
from modules.api import api

# Import CivitaiDownloader class using absolute path to avoid conflicts
import importlib.util
spec = importlib.util.spec_from_file_location(
    "civitai_downloader",
    Path(__file__).parent / "civitai_downloader.py"
)
civitai_downloader_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(civitai_downloader_module)
CivitaiDownloader = civitai_downloader_module.CivitaiDownloader

# Create separate instance for API to avoid conflicts
downloader = CivitaiDownloader()


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
    preview_path: str = None
    error: str = None


class UploadResponse(BaseModel):
    success: bool
    message: str
    filename: str = None
    path: str = None
    error: str = None


class FetchPreviewsRequest(BaseModel):
    api_key: Optional[str] = None


class FetchPreviewResult(BaseModel):
    file: str
    status: str
    preview: Optional[str] = None
    error: Optional[str] = None


class FetchPreviewsResponse(BaseModel):
    success: bool
    message: str
    total: int = 0
    downloaded: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[FetchPreviewResult] = []


def civitai_api(_: gr.Blocks, app):
    """Register API endpoints"""
    
    @app.post("/civitai/download")
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
        lora_path = None
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
                return DownloadResponse(
                    success=False,
                    message=error,
                    error=error
                )
            
            # Get model info
            model_info, error = downloader.get_model_info(version_id)
            if error:
                return DownloadResponse(
                    success=False,
                    message=error,
                    error=error
                )
            
            # Get download URL and filename
            if 'files' not in model_info or len(model_info['files']) == 0:
                return DownloadResponse(
                    success=False,
                    message="No files found for download",
                    error="No files found for download"
                )
            
            file_info = downloader.select_model_file(model_info)
            if not file_info:
                error = "No supported model file found (.safetensors, .pt, or .ckpt)"
                return DownloadResponse(
                    success=False,
                    message=error,
                    error=error
                )
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
            
            # Download file with retry mechanism
            import requests
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        # Clean up partial file before retry
                        if os.path.exists(lora_path):
                            try:
                                os.remove(lora_path)
                            except:
                                pass
                        time.sleep(retry_delay * attempt)  # Exponential backoff
                    
                    response = downloader.session.get(download_url, stream=True, timeout=300)
                    
                    if response.status_code == 401:
                        if not downloader.api_key:
                            msg = "Authorization error. Model requires API key. Get your key at: https://civitai.com/user/account"
                        else:
                            msg = "Authorization error. Check API key or get a new one at: https://civitai.com/user/account"
                        return DownloadResponse(
                            success=False,
                            message=msg,
                            error=msg
                        )
                    elif response.status_code == 403:
                        if not downloader.api_key:
                            msg = "Access forbidden. This model requires Civitai API key.\n\nSolution:\n1. Get API key: https://civitai.com/user/account\n2. Provide it in 'api_key' parameter\n3. Or create 'default_api_key.txt' file with your key"
                        else:
                            msg = "Access forbidden. Check API key validity or access rights to the model"
                        return DownloadResponse(
                            success=False,
                            message=msg,
                            error=msg
                        )
                    elif response.status_code == 404:
                        return DownloadResponse(
                            success=False,
                            message="File not found. Model may have been deleted",
                            error="File not found. Model may have been deleted"
                        )
                    elif response.status_code == 429:
                        return DownloadResponse(
                            success=False,
                            message="Download limit exceeded. Try later",
                            error="Download limit exceeded. Try later"
                        )
                    elif response.status_code != 200:
                        return DownloadResponse(
                            success=False,
                            message=f"HTTP error {response.status_code}",
                            error=f"HTTP error {response.status_code}"
                        )
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    try:
                        with open(lora_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                        
                        # Verify file was downloaded correctly
                        if not os.path.exists(lora_path):
                            raise Exception("File was not created")
                        
                        file_size = os.path.getsize(lora_path)
                        if file_size == 0:
                            if os.path.exists(lora_path):
                                os.remove(lora_path)
                            raise Exception("Downloaded empty file")
                        
                        # Verify file size matches expected size (if content-length was provided)
                        if total_size > 0 and file_size != total_size:
                            if os.path.exists(lora_path):
                                os.remove(lora_path)
                            raise Exception(f"File size mismatch: got {file_size}, expected {total_size}")
                        
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
                    return DownloadResponse(
                        success=False,
                        message="Timeout. File too large or slow connection",
                        error="Timeout. File too large or slow connection"
                    )
                
                except requests.exceptions.ConnectionError as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    if attempt < max_retries - 1:
                        continue  # Retry
                    return DownloadResponse(
                        success=False,
                        message=f"Connection lost during download: {str(e)}",
                        error=f"Connection lost during download: {str(e)}"
                    )
                
                except requests.exceptions.SSLError as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    return DownloadResponse(
                        success=False,
                        message=f"SSL connection error: {str(e)}",
                        error=f"SSL connection error: {str(e)}"
                    )
                
                except requests.exceptions.HTTPError as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    return DownloadResponse(
                        success=False,
                        message=f"HTTP error during download: {e}",
                        error=f"HTTP error during download: {e}"
                    )
                
                except requests.exceptions.RequestException as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    if attempt < max_retries - 1:
                        continue  # Retry
                    return DownloadResponse(
                        success=False,
                        message=f"Network request error: {str(e)}",
                        error=f"Network request error: {str(e)}"
                    )
                
                except OSError as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    return DownloadResponse(
                        success=False,
                        message=f"File write error: {e}. Check permissions and disk space",
                        error=f"File write error: {e}. Check permissions and disk space"
                    )
                
                except Exception as e:
                    if os.path.exists(lora_path):
                        try:
                            os.remove(lora_path)
                        except:
                            pass
                    if attempt < max_retries - 1 and "file size" not in str(e).lower() and "empty file" not in str(e).lower():
                        continue  # Retry for certain errors
                    return DownloadResponse(
                        success=False,
                        message=f"Download error: {str(e)}",
                        error=f"Download error: {str(e)}"
                    )
            else:
                # All retries exhausted
                if os.path.exists(lora_path):
                    try:
                        os.remove(lora_path)
                    except:
                        pass
                return DownloadResponse(
                    success=False,
                    message="Failed to download file after multiple attempts",
                    error="Failed to download file after multiple attempts"
                )
            
            model_name = model_info.get('model', {}).get('name', 'Unknown')
            version_name = model_info.get('name', '')

            # Download preview image
            try:
                preview_path = downloader.download_preview(model_info, lora_path)
            except Exception as e:
                model_identifier = model_info.get('model', {}).get('name', '') or model_info.get('id', 'unknown')
                print(f"[Civitai API] Warning: Failed to download preview for {model_identifier}: {e}")
                preview_path = None

            return DownloadResponse(
                success=True,
                message="Model downloaded successfully",
                filename=filename,
                path=lora_path,
                model_name=model_name,
                version_name=version_name,
                preview_path=preview_path
            )
        
        except Exception as e:
            # Final catch-all for any unexpected errors outside download loop
            if lora_path and os.path.exists(lora_path):
                try:
                    os.remove(lora_path)
                except:
                    pass
            return DownloadResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                error=f"Unexpected error: {str(e)}"
            )
    
    @app.post("/civitai/upload")
    async def upload_safetensors_file(
        file: UploadFile = File(...),
        filename: str = Form(None)
    ):
        """
        Upload a safetensors file from Telegram bot
        
        Parameters:
        - file: safetensors file (required, only .safetensors format)
        - filename: Optional custom filename (if not provided, uses original filename)
        
        Returns:
        - success: Whether upload was successful
        - message: Status message
        - filename: Saved file name
        - path: Full path to saved file
        """
        saved_path = None
        try:
            # Validate file extension
            original_filename = file.filename
            if not original_filename:
                return UploadResponse(
                    success=False,
                    message="No filename provided",
                    error="No filename provided"
                )
            
            # Check if file has .safetensors extension
            if not original_filename.lower().endswith('.safetensors'):
                return UploadResponse(
                    success=False,
                    message="Invalid file format. Only .safetensors files are allowed",
                    error=f"Invalid file format: {original_filename}. Only .safetensors files are allowed"
                )
            
            # Use custom filename if provided, otherwise use original
            final_filename = filename if filename else original_filename
            
            # Ensure custom filename also has .safetensors extension
            if filename and not final_filename.lower().endswith('.safetensors'):
                final_filename = f"{final_filename}.safetensors"
            
            # Determine save path
            from modules import shared
            save_dir = shared.cmd_opts.lora_dir if hasattr(shared.cmd_opts, 'lora_dir') else 'models/Lora'
            save_path = os.path.join(save_dir, final_filename)
            
            # Check if file already exists
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                file_size_mb = file_size / 1024 / 1024
                error_msg = (
                    f"File already exists: {final_filename}\n"
                    f"Path: {save_path}\n"
                    f"Size: {file_size_mb:.2f} MB\n"
                    f"Please use a different filename or remove the existing file first."
                )
                return UploadResponse(
                    success=False,
                    message=error_msg,
                    error=error_msg
                )
            
            # Ensure directory exists
            os.makedirs(save_dir, exist_ok=True)
            
            # Save file
            try:
                with open(save_path, 'wb') as f:
                    # Read file in chunks to handle large files
                    while True:
                        chunk = await file.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                
                # Verify file was saved correctly
                if not os.path.exists(save_path):
                    return UploadResponse(
                        success=False,
                        message="File was not saved",
                        error="File was not saved"
                    )
                
                file_size = os.path.getsize(save_path)
                if file_size == 0:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                    return UploadResponse(
                        success=False,
                        message="Uploaded empty file",
                        error="Uploaded empty file"
                    )
                
                saved_path = save_path
                
                return UploadResponse(
                    success=True,
                    message=f"File uploaded successfully ({file_size / 1024 / 1024:.2f} MB)",
                    filename=final_filename,
                    path=save_path
                )
            
            except OSError as e:
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass
                return UploadResponse(
                    success=False,
                    message=f"File write error: {e}. Check permissions and disk space",
                    error=f"File write error: {e}. Check permissions and disk space"
                )
        
        except Exception as e:
            # Clean up on error
            if saved_path and os.path.exists(saved_path):
                try:
                    os.remove(saved_path)
                except:
                    pass
            return UploadResponse(
                success=False,
                message=f"Upload error: {str(e)}",
                error=f"Upload error: {str(e)}"
            )
    
    @app.post("/civitai/fetch-previews")
    async def fetch_all_previews(request: FetchPreviewsRequest = None):
        """
        Scan all LoRA files on the node and download missing preview images from CivitAI.
        Identifies models by SHA256 hash lookup.

        Parameters:
        - api_key: Optional Civitai API key

        Returns:
        - success: Whether operation completed
        - message: Summary message
        - total: Total LoRA files without previews
        - downloaded: Number of previews downloaded
        - failed: Number of failures
        - skipped: Number of skipped (not found on CivitAI or no images)
        - results: Per-file details
        """
        try:
            api_key = None
            if request and request.api_key:
                api_key = request.api_key
            result = downloader.fetch_all_previews(api_key)
            return FetchPreviewsResponse(
                success=result.get("success", False),
                message=result.get("message", ""),
                total=result.get("total", 0),
                downloaded=result.get("downloaded", 0),
                failed=result.get("failed", 0),
                skipped=result.get("skipped", 0),
                results=[FetchPreviewResult(**r) for r in result.get("results", [])]
            )
        except Exception as e:
            return FetchPreviewsResponse(
                success=False,
                message=f"Unexpected error: {str(e)}"
            )

    @app.get("/civitai/status")
    async def get_status():
        """Health check endpoint"""
        return {"status": "online", "service": "civitai-downloader"}


def register_api():
    """Register API endpoints when app starts"""
    try:
        from modules import script_callbacks
        
        script_callbacks.on_app_started(civitai_api)
        print("[Civitai API] REST API endpoints registered")
    except Exception as e:
        print(f"[Civitai API] Failed to register API endpoints: {e}")
        import traceback
        traceback.print_exc()

# Only register if this module is imported by WebUI
try:
    from modules import script_callbacks
    register_api()
except ImportError:
    # WebUI modules not available, skip registration
    pass
