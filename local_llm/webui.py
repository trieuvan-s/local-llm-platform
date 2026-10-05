from __future__ import annotations

import base64
import hmac
import ipaddress
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import urllib.error
import urllib.request

from local_llm.settings import ROOT, load_dotenv


load_dotenv(ROOT / ".env")
GATEWAY_HOST = os.getenv("LOCAL_LLM_GATEWAY_HOST", "127.0.0.1")
if GATEWAY_HOST in {"0.0.0.0", "::"}:
    GATEWAY_HOST = "127.0.0.1"
GATEWAY = f"http://{GATEWAY_HOST}:{int(os.getenv('LOCAL_LLM_GATEWAY_PORT', '8080'))}"
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")
HOST = os.getenv("LOCAL_LLM_WEBUI_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_LLM_WEBUI_PORT", "7860"))
WEBUI_USERNAME = os.getenv("LOCAL_LLM_WEBUI_USERNAME", "").strip()
WEBUI_PASSWORD = os.getenv("LOCAL_LLM_WEBUI_PASSWORD", "").strip()
WEBUI_ALLOWED_CLIENT_CIDRS = tuple(
    ipaddress.ip_network(item.strip(), strict=False)
    for item in os.getenv("LOCAL_LLM_WEBUI_ALLOWED_CLIENT_CIDRS", "127.0.0.1/32,::1/128").split(",")
    if item.strip()
)
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

    def client_allowed(self) -> bool:
        host, *_ = self.client_address
        try:
            client_ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(client_ip in network for network in WEBUI_ALLOWED_CLIENT_CIDRS)

    def authenticated(self) -> bool:
        if not WEBUI_USERNAME or not WEBUI_PASSWORD or len(WEBUI_PASSWORD) < 12:
            return False
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(header.removeprefix("Basic ").strip(), validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, separator, password = decoded.partition(":")
        return bool(separator) and hmac.compare_digest(username, WEBUI_USERNAME) and hmac.compare_digest(password, WEBUI_PASSWORD)

    def require_access(self) -> bool:
        if not self.client_allowed():
            self.send_error(403)
            return False
        if not self.authenticated():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="FVA Local LLM WebUI"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False
        return True

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.require_access():
            return
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
        if not self.require_access():
            return
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
            tools = incoming.get("tools")
            enable_web_tools = incoming.get("enable_web_tools", False)
            auto_execute_tools = incoming.get("auto_execute_tools", False)
            temperature = incoming.get("temperature", 0.2)
            if not isinstance(messages, list) or not isinstance(think, bool):
                raise ValueError("request shape")
            if not isinstance(enable_web_tools, bool) or not isinstance(auto_execute_tools, bool):
                raise ValueError("request shape")
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
                raise ValueError("temperature")
            payload = {
                "model": model, "messages": messages, "think": think, "stream": False,
                "temperature": float(temperature), "max_tokens": 2048,
                "enable_web_tools": enable_web_tools,
                "auto_execute_tools": auto_execute_tools,
            }
            if tools is not None:
                payload["tools"] = tools
            result = gateway_request("/v1/chat/completions", payload=payload)
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
    loopbacks = {ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")}
    if not loopbacks.issubset(set(WEBUI_ALLOWED_CLIENT_CIDRS)):
        raise RuntimeError("WebUI client allowlist must include loopback")
    if HOST != "127.0.0.1" and (not WEBUI_USERNAME or len(WEBUI_PASSWORD) < 12):
        raise RuntimeError("Remote WebUI requires LOCAL_LLM_WEBUI_USERNAME and a 12+ character LOCAL_LLM_WEBUI_PASSWORD")
    print(f"Local LLM WebUI: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
