import json

from PySide6.QtCore import QByteArray, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ..config.models import AppConfig
from .providers import PROVIDERS, ProviderError


class ChatClient(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    busy_changed = Signal(bool)
    MAX_RESPONSE_BYTES = 2 * 1024 * 1024

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.reply = None
        self.busy = False
        self.generation = 0
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self._timeout)

    def _busy(self, value: bool) -> None:
        self.busy = value
        self.busy_changed.emit(value)

    def send(self, config: AppConfig, messages: list[dict], api_key: str = "") -> None:
        if self.busy:
            raise RuntimeError("已有对话请求正在进行")
        config.validate()
        if any(character in api_key for character in ("\r", "\n", "\x00")):
            self.failed.emit("API Key 含有换行或控制字符，请重新填写")
            return
        self.generation += 1
        generation = self.generation
        self._busy(True)
        if config.provider == "demo":

            def finish_demo():
                if generation == self.generation:
                    self._busy(False)
                    self.succeeded.emit(
                        "（离线演示）我听到啦！点击我可以互动，也可以试试说“谢谢你”或“晚安”。在设置中连接模型后，我就能自由聊天了。"
                    )

            QTimer.singleShot(350, finish_demo)
            return
        provider = PROVIDERS[config.provider]
        spec = provider.request(config, messages)
        request = QNetworkRequest(QUrl(spec.url))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        # Do not forward credentials across an unexpected redirect.
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        if api_key:
            request.setRawHeader(b"Authorization", ("Bearer " + api_key).encode("utf-8"))
        reply = self.manager.post(request, QByteArray(json.dumps(spec.payload).encode("utf-8")))
        self.reply = reply
        buffer = bytearray()

        def drain():
            if generation != self.generation:
                return
            buffer.extend(bytes(reply.readAll()))
            if len(buffer) > self.MAX_RESPONSE_BYTES:
                self.cancel()
                self.failed.emit("模型响应过大，请限制回复长度")

        def finish():
            if generation != self.generation:
                reply.deleteLater()
                return
            drain()
            if generation != self.generation:
                reply.deleteLater()
                return
            self.deadline.stop()
            self.reply = None
            self._busy(False)
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            try:
                if status and not 200 <= int(status) < 300:
                    raise ProviderError(f"模型服务返回 HTTP {status}；检查地址、模型名与凭据")
                if reply.error() != QNetworkReply.NetworkError.NoError:
                    raise ProviderError("无法连接模型服务；检查服务是否启动、地址和网络是否可用")
                data = json.loads(buffer)
                if not isinstance(data, dict):
                    raise ProviderError("模型响应不是 JSON 对象")
                self.succeeded.emit(provider.parse(data))
            except (ValueError, UnicodeError) as exc:
                self.failed.emit(
                    str(exc) if isinstance(exc, ProviderError) else "模型响应不是有效 JSON"
                )
            finally:
                reply.deleteLater()

        reply.readyRead.connect(drain)
        reply.finished.connect(finish)
        self.deadline.start(int(config.timeout_seconds * 1000))

    def cancel(self) -> None:
        self.generation += 1
        self.deadline.stop()
        reply, self.reply = self.reply, None
        if reply:
            reply.abort()
            reply.deleteLater()
        if self.busy:
            self._busy(False)

    def _timeout(self) -> None:
        self.cancel()
        self.failed.emit("模型请求超时，可以稍后重试或在设置中延长超时")
