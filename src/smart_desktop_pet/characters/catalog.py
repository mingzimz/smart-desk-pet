from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader

from ..config.storage import atomic_json
from ..domain.emotion import Emotion
from .artwork import render_frame


@dataclass
class Character:
    id: str
    name: str
    kind: str | None = None
    directory: Path | None = None


@dataclass
class AnimationPack:
    frames: dict[Emotion, list[QImage]]
    fps: dict[Emotion, float]


def read_image(path: Path) -> QImage:
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("图片不能超过 16 MB")
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() > 4096 or size.height() > 4096:
        raise ValueError("图片尺寸无效或超过 4096 × 4096")
    image = reader.read()
    if image.isNull():
        raise ValueError("无法读取图片，请使用 PNG、JPG 或 WebP")
    return image


class CharacterCatalog:
    def __init__(self, directory: Path):
        self.directory = directory / "characters"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.warnings: list[str] = []

    def list(self) -> list[Character]:
        self.warnings.clear()
        result = [
            Character("builtin-cat", "奶油猫 · 小团", "cat"),
            Character("builtin-rabbit", "月光兔 · 小月", "rabbit"),
        ]
        for directory in sorted(self.directory.iterdir()):
            if not directory.is_dir() or directory.name.startswith("."):
                continue
            try:
                manifest = self._manifest(directory)
                result.append(Character(directory.name, manifest["name"], directory=directory))
            except (ValueError, KeyError, TypeError, OSError):
                self.warnings.append(f"跳过无法读取的角色包：{directory.name}")
        return result

    @staticmethod
    def _manifest(directory: Path) -> dict:
        path = directory / "character.json"
        if path.stat().st_size > 128 * 1024:
            raise ValueError("角色清单过大")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("角色清单版本无效")
        if not isinstance(data.get("name"), str) or not 1 <= len(data["name"]) <= 60:
            raise ValueError("角色名称无效")
        if not isinstance(data.get("animations"), dict) or "idle" not in data["animations"]:
            raise ValueError("角色必须提供 idle 动画")
        return data

    def load(self, character: Character) -> AnimationPack:
        if character.kind:
            return AnimationPack(
                {
                    state: [render_frame(character.kind, state, n) for n in range(12)]
                    for state in Emotion
                },
                {state: 12.0 for state in Emotion},
            )
        root = character.directory.resolve()
        animations = self._manifest(root)["animations"]
        frames, fps = {}, {}
        for state in Emotion:
            spec = animations.get(state.value, animations["idle"])
            paths = spec["frames"]
            speed = spec.get("fps", 12)
            if (
                isinstance(speed, bool)
                or not isinstance(speed, (int, float))
                or not 1 <= speed <= 30
            ):
                raise ValueError("角色帧率必须为 1–30")
            if not isinstance(paths, list) or not 1 <= len(paths) <= 48:
                raise ValueError("每组动画须为 1–48 帧")
            images = []
            for filename in paths:
                if not isinstance(filename, str):
                    raise ValueError("帧路径必须是文本")
                path = (root / filename).resolve()
                if not path.is_relative_to(root):
                    raise ValueError("帧文件不能位于角色包之外")
                source = read_image(path)
                images.append(
                    source.scaled(
                        320,
                        320,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            frames[state], fps[state] = images, float(speed)
        return AnimationPack(frames, fps)

    def import_image(self, path: Path, name: str) -> Character:
        name = name.strip()
        if not 1 <= len(name) <= 60:
            raise ValueError("角色名称应为 1–60 字符")
        source = read_image(path)
        character_id = "custom-" + uuid.uuid4().hex[:12]
        destination = self.directory / character_id
        # Stage a complete pack; a failed import never enters the catalog.
        with tempfile.TemporaryDirectory(dir=self.directory, prefix=".import-") as temporary:
            staging = Path(temporary)
            animations = {}
            for state in Emotion:
                frame_paths = []
                folder = staging / state.value
                folder.mkdir()
                for index in range(8):
                    relative = f"{state.value}/{index:02d}.png"
                    if not render_frame("custom", state, index, 8, source).save(
                        str(staging / relative)
                    ):
                        raise OSError("无法写入角色图片")
                    frame_paths.append(relative)
                animations[state.value] = {"fps": 8, "frames": frame_paths}
            atomic_json(
                staging / "character.json",
                {
                    "schema_version": 1,
                    "name": name,
                    "animations": animations,
                    "source_type": "single-image-motion",
                },
            )
            staging.rename(destination)
        return Character(character_id, name, directory=destination)
