# Qwen3-14B `num_gpu=99` benchmark — 2026-08-24

## Configuration verified

- Model: `qwen3:14b`, Q4_K_M, 14.8B dense.
- Runtime context: 8,192.
- Requested `num_gpu`: 99.
- Observed offload: 41/41 layers, reported by Ollama as 100% GPU.
- Observed VRAM: about 7,802 MiB used of 8,192 MiB; about 258 MiB free.
- Thinking disabled; concurrency one.

## Five-workload result

The suite covers coding, financial arithmetic, structured JSON, Vietnamese summarization, and reasoning. Each response is capped at 256 tokens.

| Mode | Mean wall time | Generation speed | End-to-end throughput |
| --- | ---: | ---: | ---: |
| `num_gpu=99`, 41/41 layers | 63.790 s | 1.552 tok/s | 1.451 tok/s |
| Ollama auto-fit, 23/41 layers | 15.136 s | 7.499 tok/s | 6.478 tok/s |

Full offload delivered only 20.7% of the auto-fit generation speed. Mean task latency was 4.21 times longer. GPU utilization reached 99–100%, while memory utilization remained low, consistent with model data paging across PCIe because the 9.3 GB model plus runtime buffers do not fit in 8 GB VRAM.

## Quality observations

- Coding, JSON, and Vietnamese summary outputs were structurally acceptable.
- Financial arithmetic was wrong in both modes: `(90 - 64) / 64` is 40.625%, not 37.5%.
- Reasoning mixed investing/financing cash-flow hypotheses into CFO explanations.
- `num_gpu=99` changed placement and latency, not model reasoning quality.

## Decision evidence

The requested `num_gpu=99` experiment was completed and rejected as an operational configuration on the current GTX 1080 8 GB. Qwen3-14B has been restored to the measured faster Ollama auto-fit mode (23/41 layers). The subsequent Qwen3-8B comparison is recorded in `docs/QWEN3_8B_DECISION_2026-08-24.md`.

The 8B candidate was not promoted because it failed the domain-quality Decision Gate despite much higher throughput.
