from __future__ import annotations

import os
import ipaddress
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx

from local_llm.gateway import create_app
from local_llm.settings import ModelSpec, Settings


API_KEY = "a" * 64


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://upstream")
            raise httpx.HTTPStatusError("upstream", request=request, response=httpx.Response(self.status_code))


class FakeAsyncClient:
    def __init__(self) -> None:
        self.last_payload: dict | None = None
        self.loaded_models: list[str] = []
        self.unloaded_models: list[str] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, **__: object) -> FakeResponse:
        if url.endswith("/api/ps"):
            return FakeResponse({"models": [{"name": name} for name in self.loaded_models]})
        return FakeResponse({"models": [{"name": "qwen3.6:35b"}, {"name": "qwen3:14b"}, {"name": "qwen3:8b"}]})

    async def post(self, url: str, json: dict, **__: object) -> FakeResponse:
        self.last_payload = json
        if url.endswith("/api/generate"):
            self.unloaded_models.append(str(json["model"]))
            self.loaded_models = [name for name in self.loaded_models if name != json["model"]]
            return FakeResponse({"done": True})
        return FakeResponse({
            "message": {"role": "assistant", "content": '{"ok":true}',
                        "tool_calls": json.get("tool_calls", [])},
            "prompt_eval_count": 7, "eval_count": 3, "done_reason": "stop",
        })


def make_settings() -> Settings:
    models = {
        model_id: ModelSpec(model_id, model_id, model_id, ("coding", "data_analysis"), False, None)
        for model_id in ("qwen3.6:35b", "qwen3:14b", "qwen3:8b")
    }
    return Settings(API_KEY, "http://127.0.0.1:11434",
                    (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")),
                    1, 4096, 8192, models,
                    {"fva-qwen36-research-worker": "qwen3.6:35b"})


class GatewayContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = FakeAsyncClient()
        self.client = TestClient(create_app(make_settings(), lambda: self.fake))
        self.headers = {"Authorization": f"Bearer {API_KEY}"}

    def test_authentication_is_required(self) -> None:
        self.assertEqual(self.client.get("/v1/models").status_code, 401)

    def test_three_enabled_canonical_models_are_discoverable(self) -> None:
        result = self.client.get("/v1/models", headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            {item["id"] for item in result.json()["data"]},
            {"qwen3.6:35b", "qwen3:14b", "qwen3:8b"},
        )

    def test_ready_checks_all_registered_models(self) -> None:
        result = self.client.get("/health/ready", headers=self.headers)
        self.assertEqual(result.json(), {"status": "ready", "missing_models": []})

    def test_chat_maps_openai_contract_to_ollama(self) -> None:
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "qwen3:14b", "messages": [{"role": "user", "content": "Return JSON"}],
            "stream": False, "think": False, "response_format": {"type": "json_object"},
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["model"], "qwen3:14b")
        self.assertEqual(self.fake.last_payload["format"], "json")
        self.assertEqual(self.fake.last_payload["model"], "qwen3:14b")
        self.assertNotIn("num_gpu", self.fake.last_payload["options"])

    def test_unknown_model_fails_closed(self) -> None:
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "not-approved", "messages": [{"role": "user", "content": "hello"}], "stream": False,
        })
        self.assertEqual(result.status_code, 400)

    def test_switch_unloads_previous_model_before_chat(self) -> None:
        self.fake.loaded_models = ["qwen3.6:35b"]
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "qwen3:14b", "messages": [{"role": "user", "content": "hello"}], "stream": False,
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.fake.unloaded_models, ["qwen3.6:35b"])

    def test_streaming_is_rejected_explicitly(self) -> None:
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "qwen3:14b", "messages": [{"role": "user", "content": "hello"}], "stream": True,
        })
        self.assertEqual(result.status_code, 400)

    def test_tools_are_forwarded_to_ollama(self) -> None:
        tools = [{"type": "function", "function": {
            "name": "record_test_result",
            "description": "Record a result",
            "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}},
        }}]
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "qwen3:14b",
            "messages": [{"role": "user", "content": "Use a tool"}],
            "stream": False,
            "tools": tools,
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.fake.last_payload["tools"], tools)

    def test_low_temperature_is_forwarded_for_tool_calling(self) -> None:
        result = self.client.post("/v1/chat/completions", headers=self.headers, json={
            "model": "qwen3.6:35b",
            "messages": [{"role": "user", "content": "Return a tool call"}],
            "stream": False,
            "think": True,
            "temperature": 0.1,
            "tools": [{"type": "function", "function": {
                "name": "record_test_result",
                "parameters": {"type": "object", "properties": {}},
            }}],
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.fake.last_payload["options"]["temperature"], 0.1)
        self.assertTrue(self.fake.last_payload["think"])


class SettingsTests(unittest.TestCase):
    def test_registry_loads_only_with_external_secret(self) -> None:
        with patch.dict(os.environ, {"LOCAL_LLM_API_KEY": API_KEY}, clear=False):
            loaded = Settings.load()
        self.assertEqual(set(loaded.models), {"qwen3.6:35b", "qwen3:14b", "qwen3:8b"})
        self.assertIsNone(loaded.models["qwen3:8b"].num_gpu)
        self.assertIsNone(loaded.models["qwen3:14b"].num_gpu)
        self.assertIsNone(loaded.models["qwen3.6:35b"].num_gpu)


if __name__ == "__main__":
    unittest.main()
