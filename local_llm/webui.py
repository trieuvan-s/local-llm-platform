from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.error
import urllib.request

from local_llm.settings import ROOT, load_dotenv


load_dotenv(ROOT / ".env")
GATEWAY = f"http://127.0.0.1:{int(os.getenv('LOCAL_LLM_GATEWAY_PORT', '8080'))}"
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")
HOST = os.getenv("LOCAL_LLM_WEBUI_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_LLM_WEBUI_PORT", "7860"))
HTML = (Path(__file__).with_name("webui.html")).read_bytes()


def gateway_request(path: str, *, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY + path, data=data, method="GET" if data is None else "POST",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as response:
        return json.loads(response.read().decode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalLLMWebUI/1.0"

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML)))
            self.end_headers()
            self.wfile.write(HTML)
            return
        if self.path == "/api/models":
            try:
                self.send_json(gateway_request("/v1/models"))
            except Exception:
                self.send_json({"error": "Gateway chưa sẵn sàng"}, 503)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path != "/api/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256_000:
                raise ValueError("request size")
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            model = str(incoming.get("model", ""))
            messages = incoming.get("messages")
            think = incoming.get("think", False)
            if not isinstance(messages, list) or not isinstance(think, bool):
                raise ValueError("request shape")
            result = gateway_request("/v1/chat/completions", payload={
                "model": model, "messages": messages, "think": think, "stream": False,
                "temperature": 0.2, "max_tokens": 2048,
            })
            self.send_json(result)
        except (ValueError, json.JSONDecodeError):
            self.send_json({"error": "Yêu cầu không hợp lệ"}, 400)
        except urllib.error.HTTPError as exc:
            self.send_json({"error": f"Gateway từ chối yêu cầu ({exc.code})"}, 502)
        except Exception:
            self.send_json({"error": "Model local chưa phản hồi"}, 502)

    def log_message(self, *_: object) -> None:
        return


def main() -> None:
    if HOST != "127.0.0.1":
        raise RuntimeError("WebUI must remain loopback-only")
    print(f"Local LLM WebUI: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

