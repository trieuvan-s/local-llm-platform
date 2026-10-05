# Consumer integration

Hermes and Control Plane are consumers, not runtime owners.

```yaml
provider: openai_compatible
base_url: http://<tailscale-ip>:8080/v1
api_key_env: LOCAL_LLM_API_KEY
model: qwen3.6:35b  # qwen3:14b and qwen3:8b are also available
stream: false
```

The API key is stored only in `D:\trung-temp\local-llm-platform\.env`. A consumer should receive the secret through its own secret-injection mechanism, never by copying it into a tracked YAML/JSON file.

Supported phase-one routes:

- `GET /v1/models`
- `POST /v1/chat/completions` with `stream: false`
- `GET /health/ready`

Readiness and model discovery require the same Bearer token. The gateway returns the three canonical model IDs. A legacy Qwen3.6 alias is accepted for compatibility but hidden from discovery.

Model changes are expensive and serialized. Control planes should batch work by model and avoid alternating model IDs request-by-request. The queue should treat this service as a single-capacity worker.
