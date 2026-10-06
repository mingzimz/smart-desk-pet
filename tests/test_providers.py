from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest
from PySide6.QtTest import QTest

from smart_desktop_pet.ai.client import ChatClient
from smart_desktop_pet.ai.providers import OllamaProvider, OpenAICompatibleProvider, ProviderError
from smart_desktop_pet.config.models import AppConfig


@pytest.fixture
def server():
    gate = threading.Event()
    state = {"body": b"{}", "status": 200, "requests": [], "delay": False}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state["requests"].append(
                (self.path, json.loads(body), self.headers.get("Authorization"))
            )
            if state["delay"]:
                gate.wait(timeout=2)
            try:
                self.send_response(state["status"])
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(state["body"])))
                self.end_headers()
                self.wfile.write(state["body"])
            except ConnectionError:
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    state["release"] = gate.set
    yield state
    gate.set()
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


@pytest.mark.parametrize(
    "base,suffix",
    [
        ("http://localhost:11434/", "/api/chat"),
        ("http://localhost:11434/api/chat", "/api/chat"),
    ],
)
def test_ollama_endpoint(base, suffix):
    spec = OllamaProvider().request(AppConfig(base_url=base), [])
    assert spec.url == "http://localhost:11434" + suffix
    assert spec.payload["stream"] is False


def test_compatible_endpoint_and_malformed_response():
    provider = OpenAICompatibleProvider()
    for url in ("https://example.org/v1/", "https://example.org/v1/chat/completions"):
        assert (
            provider.request(AppConfig(base_url=url), []).url
            == "https://example.org/v1/chat/completions"
        )
    for data in ({}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
        with pytest.raises(ProviderError):
            provider.parse(data)


@pytest.mark.parametrize(
    "provider,path,response",
    [
        ("ollama", "/api/chat", {"message": {"content": "你好，小伙伴"}}),
        ("openai", "/chat/completions", {"choices": [{"message": {"content": "你好，小伙伴"}}]}),
    ],
)
def test_real_async_transport_with_local_stub(app, wait_until, server, provider, path, response):
    server["body"] = json.dumps(response, ensure_ascii=False).encode()
    client = ChatClient()
    answers, errors = [], []
    client.succeeded.connect(answers.append)
    client.failed.connect(errors.append)
    client.send(
        AppConfig(provider=provider, base_url=server["url"]),
        [{"role": "user", "content": "你好"}],
        "test-token",
    )
    assert client.busy
    wait_until(lambda: answers or errors)
    assert answers == ["你好，小伙伴"]
    assert not client.busy
    assert not errors
    request_path, payload, auth = server["requests"][0]
    assert request_path == path
    assert payload["messages"][0]["content"] == "你好"
    assert payload["stream"] is False
    assert auth == "Bearer test-token"


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, b'{"error":"sensitive raw server message"}', "HTTP 401"),
        (200, b"not json", "JSON"),
        (200, b'{"message": {}}', "格式"),
    ],
)
def test_transport_errors_are_user_facing(app, wait_until, server, status, body, expected):
    server.update(status=status, body=body)
    client = ChatClient()
    errors = []
    client.failed.connect(errors.append)
    client.send(AppConfig(provider="ollama", base_url=server["url"]), [])
    wait_until(lambda: errors)
    assert expected in errors[0]
    assert "sensitive" not in errors[0]
    assert not client.busy


def test_cancel_demo_drops_late_result(app):
    client = ChatClient()
    answers = []
    client.succeeded.connect(answers.append)
    client.send(AppConfig(), [])
    client.cancel()
    QTest.qWait(450)
    assert not answers
    assert not client.busy


def test_timeout_cancels_and_drops_result(app):
    client = ChatClient()
    errors, answers = [], []
    client.failed.connect(errors.append)
    client.succeeded.connect(answers.append)
    client.send(AppConfig(), [])
    client._timeout()
    QTest.qWait(450)
    assert len(errors) == 1
    assert "超时" in errors[0]
    assert not answers
    assert not client.busy


@pytest.mark.parametrize("action", ["cancel", "timeout"])
def test_pending_http_request_is_aborted(app, wait_until, server, action):
    server.update(delay=True, body=b'{"message":{"content":"late answer"}}')
    client = ChatClient()
    errors, answers = [], []
    client.failed.connect(errors.append)
    client.succeeded.connect(answers.append)
    client.send(AppConfig(provider="ollama", base_url=server["url"]), [])
    wait_until(lambda: server["requests"])
    if action == "cancel":
        client.cancel()
    else:
        client.deadline.start(20)
        wait_until(lambda: errors)
        assert "超时" in errors[0]
    server["release"]()
    QTest.qWait(100)
    assert not answers
    assert not client.busy
    assert client.reply is None


def test_oversized_http_response_releases_busy_state(app, wait_until, server):
    server["body"] = b'{"message":{"content":"' + b"x" * 2048 + b'"}}'
    client = ChatClient()
    client.MAX_RESPONSE_BYTES = 1024
    errors, answers = [], []
    client.failed.connect(errors.append)
    client.succeeded.connect(answers.append)
    client.send(AppConfig(provider="ollama", base_url=server["url"]), [])
    wait_until(lambda: errors)
    assert len(errors) == 1
    assert "过大" in errors[0]
    assert not answers
    assert not client.busy


def test_invalid_header_key_never_starts_network(app):
    client = ChatClient()
    errors = []
    client.failed.connect(errors.append)
    client.send(AppConfig(provider="ollama"), [], "secret\ninvalid")
    assert errors
    assert "secret" not in errors[0]
    assert not client.busy
    assert client.reply is None
