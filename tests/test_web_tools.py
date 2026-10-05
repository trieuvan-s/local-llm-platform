from __future__ import annotations

import ipaddress
import unittest

from fastapi.testclient import TestClient

from local_llm.gateway import create_app
from local_llm.settings import ModelSpec, Settings
from local_llm.web_tools import web_fetch


API_KEY = "a" * 64


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = ""
        self.url = "https://example.com"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("upstream error")


class FakeOllamaClient:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    async def __aenter__(self) -> "FakeOllamaClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, **__: object) -> FakeResponse:
        if url.endswith("/api/ps"):
            return FakeResponse({"models": []})
        return FakeResponse({"models": [{"name": "qwen3:8b"}]})

    async def post(self, url: str, json: dict, **__: object) -> FakeResponse:
        self.posts.append(json)
        if len(self.posts) == 1:
            return FakeResponse({
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "function": {"name": "web_search", "arguments": {"query": "qwen news"}},
                    }],
                },
                "prompt_eval_count": 10,
                "eval_count": 8,
                "done_reason": "stop",
            })
        return FakeResponse({
            "message": {"role": "assistant", "content": "Search result summarized."},
            "prompt_eval_count": 20,
            "eval_count": 5,
            "done_reason": "stop",
        })


class FakeWebClient:
    async def __aenter__(self) -> "FakeWebClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, **__: object) -> FakeResponse:
        response = FakeResponse({})
        response.text = '<a class="result__a" href="https://example.com/qwen">Qwen update</a>'
        response.url = url
        return response


def make_settings() -> Settings:
    return Settings(
        API_KEY,
        "http://127.0.0.1:11434",
        (ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")),
        1,
        4096,
        8192,
        {"qwen3:8b": ModelSpec("qwen3:8b", "qwen3:8b", "Qwen3 8B", ("test",), False)},
        {},
    )


class WebToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_web_fetch_blocks_private_urls(self) -> None:
        with self.assertRaisesRegex(ValueError, "private or local URLs are blocked"):
            await web_fetch("http://127.0.0.1:11434")


class GatewayWebToolTests(unittest.TestCase):
    def test_gateway_can_auto_execute_web_search(self) -> None:
        ollama = FakeOllamaClient()
        client = TestClient(create_app(make_settings(), lambda: ollama, lambda: FakeWebClient()))
        result = client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {API_KEY}"}, json={
            "model": "qwen3:8b",
            "messages": [{"role": "user", "content": "Find current Qwen information."}],
            "stream": False,
            "enable_web_tools": True,
            "auto_execute_tools": True,
        })
        self.assertEqual(result.status_code, 200)
        self.assertIn("tools", ollama.posts[0])
        self.assertNotIn("tools", ollama.posts[1])
        self.assertIn("Tool results from the controlled web executor", ollama.posts[1]["messages"][-1]["content"])
        self.assertTrue(result.json()["local_metrics"]["tools_auto_executed"])


if __name__ == "__main__":
    unittest.main()
