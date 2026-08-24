# Qwen local A/B report — 2026-08-24

## Test host observed

- Windows 10, dual Xeon class host, 128 GB RAM.
- Ollama 0.30.8.
- GPU reported by Ollama: NVIDIA GeForce GTX 1080, 8 GB (not GTX 1080 Ti).
- Context: 8,192; one resident model; one concurrent request; thinking disabled.
- Models: `qwen3.6:35b` (23 GB artifact) and official `qwen3:14b` Q4_K_M (9.3 GB artifact).

## Final controlled run

Raw result: `benchmarks/results/benchmark-20260824-161401.json` (local, git-ignored).

| Model | Mean wall time/task | Generation speed | End-to-end throughput |
| --- | ---: | ---: | ---: |
| Qwen3.6 35B-A3B | 153.08 s | 9.32 tok/s | 9.15 tok/s |
| Qwen3 14B | 139.44 s | 7.30 tok/s | 7.18 tok/s |

Qwen3-14B had a lower mean wall time only because it produced fewer tokens. It was about 22% slower in token generation than Qwen3.6 on this host.

## Quality review

### Coding

- Qwen3.6 implemented the requested rolling z-score logic correctly, including full-window semantics, `None`, population standard deviation, zero variance, and no look-ahead. It became overly verbose and hit the 1,400-token ceiling before finishing the sixth test and closing the answer. Assessment: logic strong, output-discipline failure.
- Qwen3-14B returned complete code and six tests, but five expected values were numerically wrong and contradicted its own implementation. For example, a non-constant rolling window was incorrectly expected to have z-score `0.0`. Assessment: not safe as an autonomous coding worker.

### Financial data analysis

- Qwen3.6 correctly calculated QoQ growth, margins, CFO/net income, and Q3 receivables/assets; it explicitly refused to fabricate Q1/Q2 total assets and identified the CFO/profit and receivables/revenue divergences. Assessment: strong draft quality; still requires deterministic calculation and source validation in production.
- Qwen3-14B calculated several headline ratios correctly, but violated the explicit missing-data rule by dividing Q1/Q2 receivables by Q3 total assets. It later contradicted that calculation in its own note. Assessment: unsuitable for autonomous financial analysis without schema validation and deterministic repair.

## Role decision

- Keep Qwen3.6 as the optional local batch research/deep-draft worker. It remains slower end-to-end than a cloud provider but was both faster per generated token and materially more reliable in this A/B.
- Keep Qwen3-14B installed and exposed only as an experimental model for short drafts, classification, extraction, and constrained JSON tasks with deterministic validation/retry. Do not promote it as the primary coding or financial-analysis agent from this result.
- For interactive routing and Telegram latency, continue using the inexpensive cloud provider during development. A smaller local model should only be added after a benchmark proves lower end-to-end latency and acceptable constraint adherence.

## Operational defect found and fixed

The original Windows stop flow left orphan `llama-server.exe` children. Three stale workers retained roughly 68 GB of committed memory and caused Qwen3.6 reload failures. The standalone stop script now terminates the complete child tree and validates cleanup within its own runtime. The gateway also serializes model changes and explicitly unloads the previous model.
