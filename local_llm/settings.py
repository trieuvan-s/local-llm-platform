from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVED_CANONICAL_MODELS = {"qwen3.6:35b", "qwen3:14b", "qwen3:8b"}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    # Windows PowerShell 5.1 writes UTF-8 files with a BOM by default.
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    ollama_model: str
    display_name: str
    roles: tuple[str, ...]
    default_thinking: bool
    num_gpu: int | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str
    ollama_base_url: str
    max_concurrency: int
    max_tokens: int
    context_length: int
    models: dict[str, ModelSpec]
    aliases: dict[str, str]

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        payload = json.loads((ROOT / "config/models.json").read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise RuntimeError("unsupported model registry schema")
        models: dict[str, ModelSpec] = {}
        for item in payload.get("models", []):
            if not isinstance(item, dict) or item.get("enabled") is not True:
                continue
            model_id = str(item["id"])
            raw_num_gpu = item.get("num_gpu")
            if raw_num_gpu is not None and (isinstance(raw_num_gpu, bool) or not isinstance(raw_num_gpu, int) or not 0 <= raw_num_gpu <= 999):
                raise RuntimeError("model num_gpu is outside approved bounds")
            models[model_id] = ModelSpec(
                model_id=model_id,
                ollama_model=str(item["ollama_model"]),
                display_name=str(item["display_name"]),
                roles=tuple(map(str, item.get("roles", []))),
                default_thinking=bool(item.get("default_thinking", False)),
                num_gpu=raw_num_gpu,
            )
        if not models:
            raise RuntimeError("at least one approved canonical model must be enabled")
        if not set(models).issubset(APPROVED_CANONICAL_MODELS):
            raise RuntimeError("model registry contains an unapproved canonical model")
        aliases = {str(k): str(v) for k, v in payload.get("compatibility_aliases", {}).items()}
        if any(target not in models for target in aliases.values()):
            raise RuntimeError("model alias target is not approved")
        api_key = os.getenv("LOCAL_LLM_API_KEY", "").strip()
        if len(api_key) < 32:
            raise RuntimeError("LOCAL_LLM_API_KEY must contain at least 32 characters")
        ollama = os.getenv("LOCAL_LLM_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        if ollama != "http://127.0.0.1:11434":
            raise RuntimeError("Ollama upstream must remain loopback-only")
        max_concurrency = int(os.getenv("LOCAL_LLM_MAX_CONCURRENCY", "1"))
        max_tokens = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "4096"))
        context_length = int(os.getenv("LOCAL_LLM_CONTEXT_LENGTH", "8192"))
        if not 1 <= max_concurrency <= 2:
            raise RuntimeError("LOCAL_LLM_MAX_CONCURRENCY must be 1 or 2")
        if not 256 <= max_tokens <= 8192 or not 2048 <= context_length <= 32768:
            raise RuntimeError("token/context limits are outside approved bounds")
        return cls(api_key, ollama, max_concurrency, max_tokens, context_length, models, aliases)

    def resolve_model(self, requested: str) -> ModelSpec:
        canonical = self.aliases.get(requested, requested)
        try:
            return self.models[canonical]
        except KeyError as exc:
            raise ValueError("model is not allowlisted") from exc
