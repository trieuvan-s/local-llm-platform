<<<<<<< HEAD
# Local LLM Platform

Standalone Windows 10 runtime for three local Qwen models behind one authenticated, OpenAI-compatible endpoint.

## Boundary

- Runtime, model blobs, configuration, logs, tests, and benchmark results live under this directory.
- Ollama is an internal loopback service on `127.0.0.1:11434`; applications must not call it directly.
- The user-facing API endpoint is the authenticated Gateway at `http://<tailscale-ip>:8080/v1` with a Bearer token stored in the local `.env`.
- The browser UI is protected with Basic Auth and runs at `http://<tailscale-ip>:7860/`; it also calls the gateway, never Ollama.
- Only one model is kept loaded at a time to fit the target host. Switching models can cause a cold-load delay.

## Models

- `qwen3.6:35b`: deeper batch research/coding/data-analysis worker.
- `qwen3:14b`: experimental coding/data-analysis/draft worker using Ollama auto-fit. The rejected full-offload experiment is documented in `docs/QWEN3_14B_FULL_GPU_BENCHMARK_2026-08-24.md`.
- `qwen3:8b`: Owner-enabled evaluation model for fast, constrained-task experiments. It failed the general replacement quality Decision Gate, so availability in WebUI/Gateway does not authorize promotion to primary coding or financial-analysis worker.

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
API base, local machine:  http://<tailscale-ip>:8080/v1
API base, remote device:   http://<tailscale-ip>:8080/v1
API key:  value of LOCAL_LLM_API_KEY in this platform's .env
Model:    qwen3.6:35b, qwen3:14b, or qwen3:8b
```

Never copy the token into source control. The compatibility alias `fva-qwen36-research-worker` remains accepted but is intentionally hidden from model discovery.

For Tailscale use, keep `LOCAL_LLM_OLLAMA_BASE_URL=http://127.0.0.1:11434`, bind `LOCAL_LLM_GATEWAY_HOST` to the host's Tailscale IP, and keep `LOCAL_LLM_ALLOWED_CLIENT_CIDRS` limited to loopback plus the Tailscale CIDR. External systems must call the Gateway, not Ollama port `11434`.

If a second Tailscale device cannot reach port `8080`, run an elevated PowerShell and execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\enable-tailscale-firewall-rule.ps1
```

For browser access from the approved Tailscale client or from the host itself, open:

```text
http://<tailscale-ip>:7860/
```

The browser will ask for credentials. Use `LOCAL_LLM_WEBUI_USERNAME` and `LOCAL_LLM_WEBUI_PASSWORD` from the local `.env`. The WebUI client allowlist is separate from the Gateway allowlist; by default it should be narrower and contain only localhost plus the approved client Tailscale IP.

The WebUI stores multiple test conversations in the browser, supports `Thinking mode`, and can send a small test function schema when `Tool Calling` is enabled. Tool calls are shown in the assistant response when the model emits them. For native Qwen tool calling, keep temperature in the `0.1` to `0.3` range; when Tool Calling is enabled, the WebUI automatically keeps the submitted temperature inside that range to reduce schema drift. Thinking mode can be enabled at the same time so Qwen3.6 can return reasoning alongside tool-call decisions.

The gateway currently rejects streaming requests explicitly. It supports non-streaming `/v1/chat/completions`, `/v1/models`, and authenticated readiness checks. This is the stable phase-one contract for organizational consumers.

## Tests

```powershell
$env:LOCAL_LLM_API_KEY=('a' * 64)
.\.runtime\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.runtime\venv\Scripts\python.exe -m compileall -q local_llm tests benchmarks
```

Benchmark output includes raw answers, wall time, token usage, and tokens/second. Quality must still be reviewed by a human; throughput alone does not determine the production role.
=======
# local-llm-platform
Dự án thiết lập nền tảng cài đặt các model LLM local trên nền tảng Ollama
>>>>>>> e909e3c98c6ff9818e3fccbbf929071cd4dc9880
