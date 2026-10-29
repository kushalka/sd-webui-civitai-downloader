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
import pytest


@pytest.mark.parametrize(
    ("model_type", "expected"),
    [
        ("Checkpoint", "custom/checkpoints"),
        ("LORA", "custom/lora"),
        ("LoCon", "custom/lora"),
        ("Embedding", "custom/embeddings"),
        ("TextualInversion", "custom/embeddings"),
    ],
)
def test_destination_matches_civitai_model_type(monkeypatch, model_type, expected):
    monkeypatch.setattr(
        module.shared,
        "cmd_opts",
        types.SimpleNamespace(
            lora_dir="custom/lora",
            ckpt_dir="custom/checkpoints",
            embeddings_dir="custom/embeddings",
        ),
        raising=False,
    )

    assert CivitaiDownloader.model_directory({"model": {"type": model_type}}) == expected


def test_unknown_model_type_is_not_routed_to_lora(monkeypatch):
    monkeypatch.setattr(
        module.shared,
        "cmd_opts",
        types.SimpleNamespace(lora_dir="custom/lora"),
        raising=False,
    )

    with pytest.raises(ValueError, match="Unsupported Civitai model type: unknown"):
        CivitaiDownloader.model_directory({"model": {"type": "Unknown"}})
