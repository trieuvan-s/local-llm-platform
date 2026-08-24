# Qwen3-8B replacement decision — 2026-08-24

## Decision Gate

Qwen3-8B may replace Qwen3-14B only when all conditions hold:

1. Generation speed improves by at least 30% on the same five workloads.
2. Coding and structured JSON outputs are valid and follow explicit constraints.
3. No material deterministic financial-calculation error.
4. At least four of five workload outputs meet domain-quality expectations.

## Direct comparison

Both models used Q4_K_M, context 8,192, thinking off, concurrency one, temperature 0.1, and the same five prompts.

| Model/mode | GPU placement | Mean wall time | Generation speed | End-to-end throughput |
| --- | --- | ---: | ---: | ---: |
| Qwen3-14B auto-fit | 23/41 layers; 57% GPU | 15.136 s | 7.499 tok/s | 6.478 tok/s |
| Qwen3-8B auto-fit | 37/37 layers; 100% GPU | 5.752 s | 28.957 tok/s | 19.825 tok/s |

Qwen3-8B is 3.86 times faster in token generation and reduced mean wall time by 62.0%.

## Quality review

- Coding: function logic was valid, but the model omitted all three required assertions. Partial fail.
- Financial arithmetic: all requested calculations were correct, including 40.63% net-income growth. Pass.
- Structured JSON: valid and complete. Pass.
- Vietnamese summary: incorrectly expanded CFO as profit before tax rather than operating cash flow. Fail.
- Reasoning: treated long-term investment and increased debt as direct explanations for CFO, confusing investing/financing flows with operating cash flow. Fail.

Quality result: fewer than four workloads passed and a material domain terminology error remained. The quality gate failed.

## Final state

- Qwen3-14B remains enabled with Ollama auto-fit.
- Qwen3-8B remains installed but is disabled in gateway discovery and routing.
- Qwen3-8B may later be reconsidered only for deterministic classification or schema-constrained extraction with validator/repair, not as a drop-in coding or financial-analysis replacement.
