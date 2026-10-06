from dataclasses import asdict, dataclass, field
import math
import re
from urllib.parse import urlsplit


DEFAULT_PERSONA = (
    "你是用户的桌面伙伴，温柔、活泼，有自己的情绪。"
    "用简短自然的中文交流。尊重用户，不声称能操作电脑或执行不存在的功能。"
)
DEFAULT_PERSONAS = {
    "builtin-cat": "你叫小团，是一只活泼的奶油猫。" + DEFAULT_PERSONA,
    "builtin-rabbit": "你叫小月，是一只安静、细心的月光兔。" + DEFAULT_PERSONA,
}


def number(value: object, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}必须是数字")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label}范围：{low}–{high}")
    return float(value)


@dataclass
class AppConfig:
    schema_version: int = 1
    provider: str = "demo"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    api_key_env: str = "SMART_PET_API_KEY"
    timeout_seconds: int = 90
    animation_speed: float = 1.0
    opacity: float = 1.0
    character_id: str = "builtin-cat"
    personas: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PERSONAS))
    position: list[int] | None = None

    @property
    def persona(self) -> str:
        return self.personas.get(self.character_id, DEFAULT_PERSONA)

    def validate(self) -> "AppConfig":
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("不支持的配置版本")
        if self.provider not in ("demo", "ollama", "openai"):
            raise ValueError("未知模型服务类型")
        if not isinstance(self.base_url, str):
            raise ValueError("模型地址必须是文本")
        url = urlsplit(self.base_url)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("模型地址须为 http:// 或 https:// URL")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("地址中不能包含密码、查询参数或片段")
        _ = url.port  # validates malformed ports
        if not isinstance(self.model, str) or not 1 <= len(self.model.strip()) <= 200:
            raise ValueError("请填写有效模型名")
        if not isinstance(self.api_key_env, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", self.api_key_env
        ):
            raise ValueError("API Key 环境变量名无效")
        number(self.timeout_seconds, 5, 300, "请求超时")
        number(self.animation_speed, 0.25, 3.0, "动画速度")
        number(self.opacity, 0.2, 1.0, "透明度")
        if not isinstance(self.character_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9_-]{1,80}", self.character_id
        ):
            raise ValueError("角色 ID 无效")
        if not isinstance(self.personas, dict) or len(self.personas) > 200:
            raise ValueError("人设配置无效")
        for key, prompt in self.personas.items():
            if (
                not isinstance(key, str)
                or not isinstance(prompt, str)
                or not 1 <= len(prompt.strip()) <= 4000
            ):
                raise ValueError("每个人设应为 1–4000 字符")
        if self.position is not None:
            if (
                not isinstance(self.position, list)
                or len(self.position) != 2
                or any(type(n) is not int for n in self.position)
            ):
                raise ValueError("窗口坐标必须为两个整数")
        return self

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        if not isinstance(data, dict):
            raise ValueError("配置必须是 JSON 对象")
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known}).validate()
