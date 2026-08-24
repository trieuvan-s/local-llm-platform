from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from local_llm.settings import Settings


MAX_BODY_BYTES = 256_000
MAX_MESSAGES = 64
MAX_MESSAGE_CHARS = 64_000


def normalize_model_name(value: object) -> str:
    return str(value or "").removesuffix(":latest")


def create_app(settings: Settings | None = None, client_factory: Any = None) -> FastAPI:
    cfg = settings or Settings.load()
    factory = client_factory or (lambda: httpx.AsyncClient(timeout=900.0))
    capacity = asyncio.Semaphore(cfg.max_concurrency)
    app = FastAPI(title="Local LLM Gateway", version="1.0.0", docs_url=None, redoc_url=None)

    def authorize(request: Request) -> None:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(status_code=403, detail="loopback access only")
        if request.headers.get("authorization", "") != f"Bearer {cfg.api_key}":
            raise HTTPException(status_code=401, detail="authentication required")

    async def unload_other_models(client: httpx.AsyncClient, target: str) -> None:
        """Serialize model swaps and wait for Ollama to release constrained RAM/VRAM."""
        response = await client.get(f"{cfg.ollama_base_url}/api/ps", timeout=5.0)
        response.raise_for_status()
        loaded = {
            normalize_model_name(item.get("name", item.get("model", "")))
            for item in response.json().get("models", [])
            if isinstance(item, dict)
        }
        others = sorted(name for name in loaded if name and name != target)
        for model in others:
            result = await client.post(f"{cfg.ollama_base_url}/api/generate", json={
                "model": model, "prompt": "", "stream": False, "keep_alive": 0,
            })
            result.raise_for_status()
        if others:
            for _ in range(40):
                await asyncio.sleep(0.5)
                current = await client.get(f"{cfg.ollama_base_url}/api/ps", timeout=5.0)
                current.raise_for_status()
                active = {
                    normalize_model_name(item.get("name", item.get("model", "")))
                    for item in current.json().get("models", [])
                    if isinstance(item, dict)
                }
                if not (active - {target}):
                    await asyncio.sleep(2.0)
                    return
            raise RuntimeError("previous model did not unload in time")

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready(request: Request) -> dict[str, Any]:
        authorize(request)
        try:
            async with factory() as client:
                response = await client.get(f"{cfg.ollama_base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            installed = {
                str(item.get("name", "")).removesuffix(":latest")
                for item in response.json().get("models", [])
                if isinstance(item, dict)
            }
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Ollama unavailable") from exc
        required = {spec.ollama_model for spec in cfg.models.values()}
        missing = sorted(required - installed)
        return {"status": "ready" if not missing else "degraded", "missing_models": missing}

    @app.get("/v1/models")
    async def models(request: Request) -> dict[str, Any]:
        authorize(request)
        return {
            "object": "list",
            "data": [
                {"id": spec.model_id, "object": "model", "owned_by": "local-ollama",
                 "display_name": spec.display_name, "roles": list(spec.roles)}
                for spec in cfg.models.values()
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> JSONResponse:
        authorize(request)
        body = await request.body()
        if not body or len(body) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="request body outside allowed bounds")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("stream", False) is not False:
            raise HTTPException(status_code=400, detail="only non-streaming JSON requests are supported")
        try:
            spec = cfg.resolve_model(str(payload.get("model", "")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        messages = payload.get("messages")
        if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_MESSAGES:
            raise HTTPException(status_code=400, detail="messages are outside allowed bounds")
        clean_messages: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}:
                raise HTTPException(status_code=400, detail="invalid message")
            content = item.get("content")
            if not isinstance(content, str) or not content or len(content) > MAX_MESSAGE_CHARS:
                raise HTTPException(status_code=400, detail="invalid message content")
            clean_messages.append({"role": str(item["role"]), "content": content})
        max_tokens = payload.get("max_tokens", 1024)
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= cfg.max_tokens:
            raise HTTPException(status_code=400, detail="max_tokens is outside allowed bounds")
        temperature = payload.get("temperature", 0.2)
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
            raise HTTPException(status_code=400, detail="temperature is outside allowed bounds")
        think = payload.get("think", spec.default_thinking)
        if not isinstance(think, bool):
            raise HTTPException(status_code=400, detail="think must be boolean")
        native: dict[str, Any] = {
            "model": spec.ollama_model, "messages": clean_messages, "stream": False,
            "think": think, "keep_alive": "30m",
            "options": {"temperature": float(temperature), "num_predict": max_tokens,
                        "num_ctx": cfg.context_length},
        }
        response_format = payload.get("response_format")
        if response_format == {"type": "json_object"}:
            native["format"] = "json"
        elif response_format is not None:
            raise HTTPException(status_code=400, detail="unsupported response_format")
        started = time.perf_counter()
        async with capacity:
            try:
                async with factory() as client:
                    await unload_other_models(client, spec.ollama_model)
                    upstream = await client.post(f"{cfg.ollama_base_url}/api/chat", json=native)
                upstream.raise_for_status()
                result = upstream.json()
            except Exception as exc:
                raise HTTPException(status_code=502, detail="local model unavailable") from exc
        elapsed = time.perf_counter() - started
        message = result.get("message") if isinstance(result.get("message"), dict) else {}
        prompt_tokens = int(result.get("prompt_eval_count", 0) or 0)
        completion_tokens = int(result.get("eval_count", 0) or 0)
        assistant: dict[str, Any] = {"role": "assistant", "content": str(message.get("content", ""))}
        thinking = str(message.get("thinking", "") or "")
        if think and thinking:
            assistant["reasoning_content"] = thinking
        eval_seconds = float(result.get("eval_duration", 0) or 0) / 1_000_000_000
        end_to_end_tps = completion_tokens / elapsed if elapsed else 0.0
        generation_tps = completion_tokens / eval_seconds if eval_seconds else 0.0
        return JSONResponse({
            "id": "chatcmpl-local", "object": "chat.completion", "created": int(time.time()),
            "model": spec.model_id,
            "choices": [{"index": 0, "message": assistant,
                         "finish_reason": "length" if result.get("done_reason") == "length" else "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens},
            "local_metrics": {
                "wall_seconds": round(elapsed, 3),
                "load_seconds": round(float(result.get("load_duration", 0) or 0) / 1_000_000_000, 3),
                "prompt_eval_seconds": round(float(result.get("prompt_eval_duration", 0) or 0) / 1_000_000_000, 3),
                "generation_seconds": round(eval_seconds, 3),
                "generation_tokens_per_second": round(generation_tps, 3),
                "end_to_end_tokens_per_second": round(end_to_end_tps, 3),
                "thinking_enabled": think,
            },
        })

    return app


app = create_app()
