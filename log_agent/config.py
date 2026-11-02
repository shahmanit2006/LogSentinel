from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"

def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["ollama_base_url"] = os.getenv("OLLAMA_BASE_URL", cfg["ollama_base_url"]).rstrip("/")
    cfg["ollama_model"] = os.getenv("OLLAMA_MODEL", cfg["ollama_model"])
    cfg["embedding_model"] = os.getenv("EMBEDDING_MODEL", cfg["embedding_model"])
    cfg["qdrant_path"] = os.getenv("QDRANT_PATH", cfg["qdrant_path"])
    cfg["sqlite_path"] = os.getenv("SQLITE_PATH", cfg["sqlite_path"])
    for key in ("qdrant_path", "sqlite_path"):
        p = Path(cfg[key])
        if not p.is_absolute():
            cfg[key] = str(ROOT / p)
    Path(cfg["qdrant_path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["sqlite_path"]).parent.mkdir(parents=True, exist_ok=True)
    return cfg
