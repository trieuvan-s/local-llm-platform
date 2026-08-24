from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import statistics
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    for raw in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if raw and not raw.lstrip().startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def call_gateway(model: str, case: dict) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "stream": False, "think": False, "temperature": 0.1, "max_tokens": case["max_tokens"],
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8080/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {os.environ['LOCAL_LLM_API_KEY']}", "Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=1800) as response:
        payload = json.loads(response.read().decode("utf-8"))
    payload["client_wall_seconds"] = round(time.perf_counter() - started, 3)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["qwen3.6:35b", "qwen3:14b"])
    parser.add_argument("--cases", default="benchmarks/cases.json")
    args = parser.parse_args()
    load_env()
    cases_path = (ROOT / args.cases).resolve()
    if ROOT not in cases_path.parents:
        raise ValueError("benchmark cases must remain inside the platform repository")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    records = []
    for model in args.models:
        warmup = {"prompt": "Return exactly: READY", "max_tokens": 16}
        print(f"Warming {model}...", flush=True)
        call_gateway(model, warmup)
        for case in cases:
            print(f"Running {model} / {case['id']}...", flush=True)
            result = call_gateway(model, case)
            records.append({
                "model": model, "case_id": case["id"], "category": case["category"],
                "wall_seconds": result["client_wall_seconds"],
                "load_seconds": result.get("local_metrics", {}).get("load_seconds", 0),
                "generation_tokens_per_second": result.get("local_metrics", {}).get("generation_tokens_per_second", 0),
                "end_to_end_tokens_per_second": result.get("local_metrics", {}).get("end_to_end_tokens_per_second", 0),
                "usage": result.get("usage", {}),
                "answer": result["choices"][0]["message"]["content"],
            })
    summary = {}
    for model in args.models:
        rows = [row for row in records if row["model"] == model]
        summary[model] = {
            "mean_wall_seconds": round(statistics.mean(row["wall_seconds"] for row in rows), 3),
            "mean_generation_tokens_per_second": round(statistics.mean(row["generation_tokens_per_second"] for row in rows), 3),
            "mean_end_to_end_tokens_per_second": round(statistics.mean(row["end_to_end_tokens_per_second"] for row in rows), 3),
        }
    output = {"generated_at": datetime.now(timezone.utc).isoformat(), "summary": summary, "records": records}
    target = ROOT / "benchmarks/results" / f"benchmark-{cases_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result_file": str(target), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
