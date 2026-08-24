# Standalone architecture

```text
Hermes / Control Plane / local WebUI
                 |
                 | OpenAI-compatible + Bearer
                 v
       127.0.0.1:8080/v1
        Local LLM Gateway
       - two-model allowlist
       - request bounds
       - concurrency = 1
       - model-switch lock
       - explicit unload + wait
                 |
                 | internal Ollama API
                 v
       127.0.0.1:11434
              Ollama
          /             \
 qwen3.6:35b          qwen3:14b
 (one resident model at a time)
```

The WebUI on `127.0.0.1:7860` is a consumer of the gateway. It does not know the Ollama endpoint or the API token. External consumers must never use port 11434.

On the current Windows host, switching from one large model to another must be serialized. The gateway asks Ollama to unload the previous resident model and waits before loading the next. The stop script terminates the full Ollama child-process tree to prevent orphan `llama-server` processes from retaining committed memory.

This phase binds all ports to loopback. It is suitable for Hermes and Control Plane processes on the same host. Remote-host access requires a separately approved authenticated reverse proxy, firewall allowlist, TLS, and secret rotation; do not bind Ollama publicly.
