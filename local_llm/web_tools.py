from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import ipaddress
import json
import socket
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

import httpx


MAX_SEARCH_RESULTS = 5
MAX_FETCH_CHARS = 12_000
MAX_QUERY_CHARS = 300
MAX_URL_CHARS = 2_000
WEB_TIMEOUT_SECONDS = 12.0
USER_AGENT = "LocalLLMPlatform/1.0"


WEB_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the public web for current information. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": MAX_SEARCH_RESULTS},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch one public HTTP or HTTPS URL and return readable text plus basic metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Public URL to fetch."},
                    "max_chars": {"type": "integer", "minimum": 500, "maximum": MAX_FETCH_CHARS},
                },
                "required": ["url"],
            },
        },
    },
]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = (self.title + " " + text).strip()
        elif not self._skip_depth:
            self.parts.append(text)

    def text(self) -> str:
        compact = "\n".join(line.strip() for line in " ".join(self.parts).splitlines())
        return "\n".join(line for line in compact.splitlines() if line)


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        class_name = values.get("class", "")
        if tag == "a" and "result__a" in class_name:
            self._active = {"title": "", "url": _unwrap_ddg_url(values.get("href", "")), "snippet": ""}
            self._capture_title = True
        elif self._active is not None and "result__snippet" in class_name:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self._capture_title = False
            if self._active and self._active["title"] and self._active["url"]:
                self.results.append(self._active)
            self._active = None
        elif self._capture_snippet and tag in {"a", "div"}:
            self._capture_snippet = False

    def handle_data(self, data: str) -> None:
        if self._active is None:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._capture_title:
            self._active["title"] = (self._active["title"] + " " + text).strip()
        elif self._capture_snippet:
            self._active["snippet"] = (self._active["snippet"] + " " + text).strip()


def build_web_result_message(results: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Tool results from the controlled web executor. Use these results as references, "
            "cite URLs when useful, and say when the evidence is insufficient.\n"
            + json.dumps(results, ensure_ascii=False)
        ),
    }


async def execute_web_tool_call(tool_call: dict[str, Any], client_factory: Any | None = None) -> dict[str, Any]:
    function = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    name = str(function.get("name", ""))
    arguments = _parse_arguments(function.get("arguments", {}))
    try:
        if name == "web_search":
            result = await web_search(str(arguments.get("query", "")), int(arguments.get("max_results", MAX_SEARCH_RESULTS)), client_factory)
        elif name == "web_fetch":
            result = await web_fetch(str(arguments.get("url", "")), int(arguments.get("max_chars", MAX_FETCH_CHARS)), client_factory)
        else:
            result = {"ok": False, "error": f"unsupported tool: {name}"}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    return {"tool_call_id": str(tool_call.get("id", "")), "name": name, "result": result}


async def web_search(query: str, max_results: int = MAX_SEARCH_RESULTS, client_factory: Any | None = None) -> dict[str, Any]:
    clean_query = " ".join(query.split())[:MAX_QUERY_CHARS]
    if not clean_query:
        raise ValueError("query is required")
    limit = max(1, min(MAX_SEARCH_RESULTS, max_results))
    url = f"https://duckduckgo.com/html/?q={quote_plus(clean_query)}"
    async with _web_client(client_factory) as client:
        response = await client.get(url, follow_redirects=True, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    response.raise_for_status()
    parser = _DuckDuckGoParser()
    parser.feed(response.text)
    results = []
    for item in parser.results:
        if _is_public_url(item["url"]):
            results.append(item)
        if len(results) >= limit:
            break
    return {"ok": True, "query": clean_query, "results": results}


async def web_fetch(url: str, max_chars: int = MAX_FETCH_CHARS, client_factory: Any | None = None) -> dict[str, Any]:
    clean_url = url.strip()[:MAX_URL_CHARS]
    await _ensure_public_url_resolves(clean_url)
    limit = max(500, min(MAX_FETCH_CHARS, max_chars))
    async with _web_client(client_factory) as client:
        response = await client.get(clean_url, follow_redirects=True, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain"})
    response.raise_for_status()
    final_url = str(response.url)
    await _ensure_public_url_resolves(final_url)
    content_type = response.headers.get("content-type", "")
    text = response.text
    title = ""
    if "html" in content_type.lower():
        parser = _TextExtractor()
        parser.feed(text[:250_000])
        title = parser.title
        text = parser.text()
    return {"ok": True, "url": final_url, "content_type": content_type, "title": title, "text": text[:limit]}


def _web_client(client_factory: Any | None) -> httpx.AsyncClient:
    if client_factory is not None:
        return client_factory()
    return httpx.AsyncClient(timeout=WEB_TIMEOUT_SECONDS)


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _unwrap_ddg_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return target or value
    return value


def _is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def _ensure_public_url_resolves(value: str) -> None:
    if not _is_public_url(value):
        raise ValueError("only public http/https URLs are allowed")
    host = urlparse(value).hostname
    if not host:
        raise ValueError("URL host is required")
    try:
        ip = ipaddress.ip_address(host)
        if _is_blocked_ip(ip):
            raise ValueError("private or local URLs are blocked")
        return
    except ValueError as exc:
        if "blocked" in str(exc):
            raise
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    for *_prefix, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_blocked_ip(ip):
            raise ValueError("private or local URLs are blocked")


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
