import importlib.util
import sys
import types
from pathlib import Path


modules = types.ModuleType("modules")
modules.shared = types.SimpleNamespace()
modules.scripts = types.SimpleNamespace(basedir=lambda: str(Path.cwd()))
sys.modules.setdefault("modules", modules)

spec = importlib.util.spec_from_file_location(
    "civitai_downloader",
    Path(__file__).parents[1] / "scripts" / "civitai_downloader.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CivitaiDownloader = module.CivitaiDownloader


def test_selects_primary_model_instead_of_training_archive():
    files = {
        "files": [
            {
                "name": "Tsaritsa.zip",
                "type": "Training Data",
                "downloadUrl": "https://example.test/training",
            },
            {
                "name": "Tsaritsa_Genshin_Impact_IL_epoch_20.safetensors",
                "type": "Model",
                "primary": True,
                "downloadUrl": "https://example.test/model",
            },
        ]
    }

    selected = CivitaiDownloader.select_model_file(files)

    assert selected["name"] == "Tsaritsa_Genshin_Impact_IL_epoch_20.safetensors"


def test_prefers_primary_model_among_supported_files():
    files = {
        "files": [
            {"name": "old.ckpt", "type": "Model", "primary": False},
            {"name": "current.safetensors", "type": "Model", "primary": True},
        ]
    }

    assert CivitaiDownloader.select_model_file(files)["name"] == "current.safetensors"


def test_rejects_version_with_only_auxiliary_files():
    files = {
        "files": [
            {"name": "training.zip", "type": "Training Data"},
            {"name": "readme.txt", "type": "Training Data"},
        ]
    }

    assert CivitaiDownloader.select_model_file(files) is None
