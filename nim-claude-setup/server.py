#!/usr/bin/env python3
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PORT = int(os.getenv("NIM_PROXY_PORT", "8090"))
NIM_BASE_URL = os.getenv("NIM_API_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
NIM_TIMEOUT_SECONDS = float(os.getenv("NIM_PROXY_TIMEOUT", "45"))
PRIMARY_MODEL = os.getenv("NIM_PRIMARY_MODEL", os.getenv("NIM_DEFAULT_MODEL", "qwen/qwen3-coder-480b-a35b-instruct"))
SECONDARY_MODEL = os.getenv("NIM_SECONDARY_MODEL", "qwen/qwen2.5-coder-32b-instruct")
PRIMARY_FALLBACK_MODEL = os.getenv("NIM_PRIMARY_FALLBACK_MODEL", SECONDARY_MODEL)
PRIMARY_DISPLAY_NAME = os.getenv("NIM_PRIMARY_DISPLAY_NAME", "Qwen 3 Coder 480B (Default)")
SECONDARY_DISPLAY_NAME = os.getenv("NIM_SECONDARY_DISPLAY_NAME", "Qwen 2.5 Coder 32B (Secondary)")
MAX_OUTPUT_TOKENS = int(os.getenv("NIM_MAX_OUTPUT_TOKENS", "768"))


def _utc_iso_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _canon_model_name(value):
    if not isinstance(value, str):
        return ""
    return value.lower().replace("_", "-").replace(" ", "")


def _nim_api_key(headers):
    for name in ("NIM_API_KEY", "NVIDIA_API_KEY", "MISTRAL_API_KEY"):
        value = os.getenv(name)
        if isinstance(value, str) and value.strip():
            return value.strip()

    x_key = headers.get("x-api-key", "").strip()
    if x_key and x_key.lower() != "dummy":
        return x_key

    auth = headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token and token.lower() != "dummy":
            return token
    return ""


def _as_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            parts.append(item["text"])
        elif item.get("type") == "tool_result":
            nested = item.get("content")
            if isinstance(nested, str):
                parts.append(nested)
            elif isinstance(nested, list):
                for sub in nested:
                    if isinstance(sub, dict) and sub.get("type") == "text" and isinstance(sub.get("text"), str):
                        parts.append(sub["text"])
    return "\n".join(p for p in parts if p)


def _to_openai_messages(body):
    messages = []

    system = body.get("system")
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system})
    elif isinstance(system, list):
        chunks = []
        for item in system:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                chunks.append(item["text"])
        if chunks:
            messages.append({"role": "system", "content": "\n".join(chunks)})

    for msg in body.get("messages", []):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        if role not in ("user", "assistant", "system", "tool"):
            role = "user"
        messages.append({"role": role, "content": _as_text(msg.get("content"))})

    if not messages:
        messages = [{"role": "user", "content": ""}]
    return messages


def _normalize_model(model):
    if not isinstance(model, str) or not model.strip():
        return PRIMARY_MODEL
    raw = model.strip()
    low = _canon_model_name(raw)

    # Secondary aliases: keep this before generic "claude-*" handling.
    secondary_aliases = {
        _canon_model_name(SECONDARY_MODEL),
        "haiku",
        "claude-haiku",
        "secondary",
        "backup",
        "qwen25-coder-32b-secondary",
        "nim-secondary-default",
        "nim-secondary-coding",
        "nim-qwen25-secondary",
        "qwen25coder",
        "qwen-2.5-coder",
        "qwen2.5coder32b",
        "qwen-2.5-coder-32b",
    }
    if low in secondary_aliases or "haiku" in low:
        return SECONDARY_MODEL

    # Primary aliases.
    primary_aliases = {
        _canon_model_name(PRIMARY_MODEL),
        "qwen3-coder-480b-primary",
        "nim-primary-default",
        "nim-qwen3-primary",
        "qwen3coder",
        "qwen-3-coder",
        "qwen3coder480b",
        "qwen-3-coder-480b",
        "qwen348b",
        "qwen-3-48b",
        "qwen3480b",
        "qwen-3-480b",
        "primary",
        "default",
        "nim-glm5-default",
    }
    if low in primary_aliases or "sonnet" in low or "opus" in low:
        return PRIMARY_MODEL

    # Claude model picker mapping:
    # - Opus/Sonnet -> primary
    # - Haiku -> secondary
    if low.startswith("claude-"):
        return PRIMARY_MODEL

    return raw


def _model_catalog():
    created_at = _utc_iso_now()
    models = [
        {
            "id": "qwen3-coder-480b-primary",
            "type": "model",
            "display_name": PRIMARY_DISPLAY_NAME,
            "created_at": created_at,
            "upstream_model": PRIMARY_MODEL,
        },
        {
            "id": "qwen25-coder-32b-secondary",
            "type": "model",
            "display_name": SECONDARY_DISPLAY_NAME,
            "created_at": created_at,
            "upstream_model": SECONDARY_MODEL,
        },
    ]
    return {
        "data": models,
        "has_more": False,
        "first_id": models[0]["id"],
        "last_id": models[-1]["id"],
    }


def _extract_nim_text(response_json):
    if not isinstance(response_json, dict):
        return ""
    choices = response_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)

    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str):
        return reasoning

    text = first.get("text")
    if isinstance(text, str):
        return text

    return ""


def _nim_request(path, api_key, payload=None):
    url = f"{NIM_BASE_URL}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "nim-claude-proxy/1.0",
    }

    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        method = "POST"

    req = Request(url=url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=NIM_TIMEOUT_SECONDS) as resp:
            return resp.getcode(), resp.read(), dict(resp.headers)
    except HTTPError as err:
        return err.code, err.read(), dict(err.headers)
    except URLError as err:
        return 0, json.dumps({"error": {"message": str(err)}}).encode("utf-8"), {}
    except TimeoutError as err:
        return 0, json.dumps({"error": {"message": str(err)}}).encode("utf-8"), {}
    except OSError as err:
        return 0, json.dumps({"error": {"message": str(err)}}).encode("utf-8"), {}


def _chunk_text(text, size=320):
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


class Handler(BaseHTTPRequestHandler):
    server_version = "nim-claude-proxy/1.0"

    def log_message(self, fmt, *args):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {self.address_string()} {fmt % args}")

    def _send_json(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self):
        length = _safe_int(self.headers.get("Content-Length", "0"), 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return None

    def _send_error(self, status, msg, err_type="api_error"):
        self._send_json(status, {"type": "error", "error": {"type": err_type, "message": msg}})

    def _sse_event(self, event_name, payload):
        data = json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {
                "status": "ok",
                "timestamp": _utc_iso_now(),
                "proxy": "nim-claude-proxy",
                "port": PORT,
                "nim_base_url": NIM_BASE_URL,
                "default_model": PRIMARY_MODEL,
                "secondary_model": SECONDARY_MODEL,
                "primary_fallback_model": PRIMARY_FALLBACK_MODEL,
                "default_display_name": PRIMARY_DISPLAY_NAME,
                "secondary_display_name": SECONDARY_DISPLAY_NAME,
                "has_api_key": bool(_nim_api_key(self.headers)),
            })
            return

        if path == "/v1/models":
            self._send_json(200, _model_catalog())
            return

        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/v1/messages":
            self._send_json(404, {"error": "not_found"})
            return

        body = self._read_json()
        if body is None:
            self._send_error(400, "Invalid JSON request body.", "invalid_request_error")
            return

        api_key = _nim_api_key(self.headers)
        if not api_key:
            self._send_error(401, "Missing NVIDIA API key. Set NIM_API_KEY or NVIDIA_API_KEY.", "authentication_error")
            return

        started = time.time()
        model = _normalize_model(body.get("model"))
        requested_max_tokens = _safe_int(body.get("max_tokens", 4096), 4096)
        max_tokens = max(1, min(requested_max_tokens, MAX_OUTPUT_TOKENS))
        stream = bool(body.get("stream", False))

        nim_payload = {
            "model": model,
            "messages": _to_openai_messages(body),
            "max_tokens": max_tokens,
            "stream": False,
        }
        if "temperature" in body:
            nim_payload["temperature"] = body["temperature"]
        if "top_p" in body:
            nim_payload["top_p"] = body["top_p"]

        print(
            f"[nim-claude-proxy] request model={model} stream={stream} "
            f"max_tokens_requested={requested_max_tokens} max_tokens_sent={max_tokens}",
            flush=True,
        )

        status, nim_body, _ = _nim_request("chat/completions", api_key, nim_payload)
        if status == 0 and model == PRIMARY_MODEL and PRIMARY_FALLBACK_MODEL and PRIMARY_FALLBACK_MODEL != PRIMARY_MODEL:
            fallback_model = PRIMARY_FALLBACK_MODEL
            print(
                f"[nim-claude-proxy] primary model unavailable, falling back to {fallback_model}",
                flush=True,
            )
            nim_payload["model"] = fallback_model
            model = fallback_model
            status, nim_body, _ = _nim_request("chat/completions", api_key, nim_payload)

        if status == 0:
            self._send_error(502, "Unable to reach NVIDIA NIM API.")
            return
        if status >= 400:
            msg = "NVIDIA NIM API request failed."
            try:
                parsed = json.loads(nim_body.decode("utf-8"))
                if isinstance(parsed, dict):
                    err = parsed.get("error")
                    if isinstance(err, dict) and isinstance(err.get("message"), str):
                        msg = err["message"]
            except Exception:
                pass
            self._send_error(status, msg)
            return

        try:
            nim_json = json.loads(nim_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_error(502, "NVIDIA NIM API returned non-JSON response.")
            return

        text = _extract_nim_text(nim_json)
        usage = nim_json.get("usage") if isinstance(nim_json.get("usage"), dict) else {}
        in_tok = _safe_int(usage.get("prompt_tokens", 0), 0)
        out_tok = _safe_int(usage.get("completion_tokens", 0), 0)
        msg_id = f"msg_{uuid.uuid4().hex}"
        elapsed_ms = int((time.time() - started) * 1000)
        print(
            f"[nim-claude-proxy] response status=200 elapsed_ms={elapsed_ms} "
            f"input_tokens={in_tok} output_tokens={out_tok}",
            flush=True,
        )

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            self._sse_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": in_tok, "output_tokens": 0},
                },
            })
            self._sse_event("content_block_start", {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            })
            for chunk in _chunk_text(text):
                self._sse_event("content_block_delta", {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": chunk},
                })
            self._sse_event("content_block_stop", {"type": "content_block_stop", "index": 0})
            self._sse_event("message_delta", {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                "usage": {"output_tokens": out_tok},
            })
            self._sse_event("message_stop", {"type": "message_stop"})
            # Anthropic SDK clients may wait for stream EOF even after message_stop.
            # Explicitly close the socket so streaming callers terminate promptly.
            self.wfile.flush()
            self.close_connection = True
            return

        self._send_json(200, {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        })


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"nim-claude-proxy listening on http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
