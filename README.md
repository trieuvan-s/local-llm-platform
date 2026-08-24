# Local LLM Platform

Standalone Windows 10 runtime for exactly two local Qwen models behind one authenticated, OpenAI-compatible endpoint.

## Boundary

- Runtime, model blobs, configuration, logs, tests, and benchmark results live under this directory.
- Ollama is an internal loopback service on `127.0.0.1:11434`; applications must not call it directly.
- The only consumer endpoint is `http://127.0.0.1:8080/v1` with a Bearer token stored in the local `.env`.
- The local WebUI is `http://127.0.0.1:7860` and also calls the gateway, never Ollama.
- Only one model is kept loaded at a time to fit the target host. Switching models can cause a cold-load delay.

## Models

- `qwen3.6:35b`: deeper batch research/coding/data-analysis worker.
- `qwen3:14b`: faster coding/data-analysis/draft worker for the A/B evaluation.

## Windows commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1 -OpenWebUI
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pull-models.ps1 -SkipQwen36
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\status.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration-test.ps1 -Model qwen3:14b
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-startup-task.ps1
.\.runtime\venv\Scripts\python.exe .\benchmarks\run_benchmark.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

The one-time migration from the stock assistant repository is deliberately separate:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate-runtime.ps1 -StockProjectRoot D:\codex-workspace\stock-advisor-assitant
```

## Consumer contract

Configure Hermes or a Control Plane with:

```text
API base: http://127.0.0.1:8080/v1
API key:  value of LOCAL_LLM_API_KEY in this platform's .env
Model:    qwen3:14b or qwen3.6:35b
```

Never copy the token into source control. The compatibility alias `fva-qwen36-research-worker` remains accepted but is intentionally hidden from model discovery.

The gateway currently rejects streaming requests explicitly. It supports non-streaming `/v1/chat/completions`, `/v1/models`, and authenticated readiness checks. This is the stable phase-one contract for organizational consumers.

## Tests

```powershell
$env:LOCAL_LLM_API_KEY=('a' * 64)
.\.runtime\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.runtime\venv\Scripts\python.exe -m compileall -q local_llm tests benchmarks
```

Benchmark output includes raw answers, wall time, token usage, and tokens/second. Quality must still be reviewed by a human; throughput alone does not determine the production role.
