# Standalone architecture

```text
Hermes / Control Plane / local WebUI
                 |
                 | OpenAI-compatible + Bearer
                 v
       <tailscale-ip>:8080/v1
        Local LLM Gateway
       - three-model allowlist
       - request bounds
       - concurrency = 1
       - model-switch lock
       - explicit unload + wait
                 |
                 | internal Ollama API
                 v
       127.0.0.1:11434
              Ollama
          /       |       \
 qwen3.6:35b   qwen3:14b   qwen3:8b
 (one resident model at a time)
```

The WebUI on `<tailscale-ip>:7860` is a consumer of the gateway. It does not know the Ollama endpoint or the API token. External consumers must never use port 11434.

On the current Windows host, switching from one large model to another must be serialized. The gateway asks Ollama to unload the previous resident model and waits before loading the next. The stop script terminates the full Ollama child-process tree to prevent orphan `llama-server` processes from retaining committed memory.

Tailscale access is supported through the authenticated Gateway only. Ollama remains loopback-only on `127.0.0.1:11434`; both local and remote consumers must call `http://<tailscale-ip>:8080/v1` with the Bearer token from the local `.env`. The Gateway enforces the configured client CIDR allowlist before forwarding to Ollama. The WebUI is available on the same Tailscale-bound host port and follows the same access pattern.
