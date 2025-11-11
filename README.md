# Civitai Downloader REST API for Stable Diffusion WebUI

REST API extension for downloading Civitai models via HTTP requests.

## Features

- 📥 Download models from Civitai via REST API
- 🔑 Support for Civitai API keys
- 🤖 Telegram bot integration ready
- 💾 Automatic saving to Lora folder

## Installation

```bash
cd extensions
git clone https://github.com/kushalka/sd-webui-civitai-downloader.git
```

Restart Stable Diffusion WebUI with `--api` flag.

## Usage

### Start WebUI with API enabled

```bash
python webui.py --api --listen
```

## API Endpoints

### Check Status
```bash
curl http://localhost:7860/civitai/status
```

### Download Model
```bash
curl -X POST http://localhost:7860/civitai/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://civitai.com/models/123456",
    "api_key": "your_civitai_api_key"
  }'
```

### Python Example
```python
import requests

response = requests.post(
    "http://localhost:7860/civitai/download",
    json={
        "url": "https://civitai.com/models/123456",
        "api_key": "your_civitai_api_key"
    }
)

result = response.json()
if result["success"]:
    print(f"Downloaded: {result['filename']}")
else:
    print(f"Error: {result['error']}")
```

## Documentation

- [API_INTEGRATION.md](API_INTEGRATION.md) - Full API documentation
- [telegram_bot_example.py](telegram_bot_example.py) - Telegram bot examples

## License

MIT
