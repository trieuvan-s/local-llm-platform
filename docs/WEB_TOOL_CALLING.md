# Web tool calling

The Gateway can expose controlled web tools to Qwen for requests that need fresh references.

Available built-in tools:

- `web_search`: searches the public web and returns titles, URLs, and snippets.
- `web_fetch`: fetches one public HTTP/HTTPS URL and returns readable text.

Enable web tools per `/v1/chat/completions` request:

```json
{
  "enable_web_tools": true,
  "auto_execute_tools": true
}
```

When enabled, Qwen may emit a `tool_calls` entry for `web_search` or `web_fetch`. The Gateway executes supported web calls, blocks private/local URLs, appends the controlled tool results to the conversation, and asks the model for a final answer.

The final response includes `choices[0].message.tool_results` when a supported web tool was executed. This keeps source data auditable by the caller.

Requests that omit these flags keep the older behavior: the Gateway forwards caller-provided tools to Ollama but does not execute them.

Security limits:

- Only `http` and `https` URLs are allowed.
- Localhost, private IPs, link-local, multicast, reserved, and unspecified addresses are blocked.
- Search queries, fetched URLs, fetched text, tool count, and tool JSON size are bounded.
- Web requests use a short timeout and a platform user agent.
