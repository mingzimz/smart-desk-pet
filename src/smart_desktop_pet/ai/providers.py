from dataclasses import dataclass
from typing import Protocol

from ..config.models import AppConfig


class ProviderError(ValueError):
    pass


@dataclass(frozen=True)
class RequestSpec:
    url: str
    payload: dict


class ChatProvider(Protocol):
    def request(self, config: AppConfig, messages: list[dict]) -> RequestSpec: ...
    def parse(self, data: dict) -> str: ...


def content(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError("模型未返回文本；请检查模型是否支持普通文本对话")
    if len(value) > 8000:
        raise ProviderError("回复超过 8000 字符，请要求模型简短回复")
    return value.strip()


class OllamaProvider:
    def request(self, config: AppConfig, messages: list[dict]) -> RequestSpec:
        base = config.base_url.rstrip("/")
        url = base if base.endswith("/api/chat") else f"{base}/api/chat"
        return RequestSpec(
            url,
            {
                "model": config.model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": 1024},
            },
        )

    def parse(self, data: dict) -> str:
        try:
            return content(data["message"]["content"])
        except (KeyError, TypeError, IndexError) as exc:
            raise ProviderError("Ollama 返回格式无效") from exc


class OpenAICompatibleProvider:
    def request(self, config: AppConfig, messages: list[dict]) -> RequestSpec:
        base = config.base_url.rstrip("/")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        return RequestSpec(url, {"model": config.model, "messages": messages, "stream": False})

    def parse(self, data: dict) -> str:
        try:
            return content(data["choices"][0]["message"]["content"])
        except (KeyError, TypeError, IndexError) as exc:
            raise ProviderError("OpenAI 兼容服务返回格式无效") from exc


PROVIDERS: dict[str, ChatProvider] = {
    "ollama": OllamaProvider(),
    "openai": OpenAICompatibleProvider(),
}
