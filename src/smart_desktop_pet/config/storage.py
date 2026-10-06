import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime
from typing import Callable

from .models import AppConfig


class StorageError(RuntimeError):
    pass


def data_directory() -> Path:
    override = os.environ.get("SMART_PET_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(os.environ.get("APPDATA", str(Path.home() / ".config")))
    return root / "SmartDesktopPet"


def atomic_json(path: Path, data: dict) -> None:
    """Write next to the destination then replace it, never truncate the live file."""
    temp: str | None = None
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as file:
            temp = file.name
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    except (OSError, ValueError, TypeError) as exc:
        raise StorageError(f"无法保存 {path.name}：{exc}") from exc
    finally:
        if temp and os.path.exists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass  # A leftover temp file must not hide the original save error.


def load_json(
    path: Path, default: dict, validate: Callable[[dict], object]
) -> tuple[dict, str | None]:
    if not path.exists():
        return default, None
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("JSON 文件超过 5 MB")
        data = json.loads(path.read_text(encoding="utf-8"))
        validate(data)
        return data, None
    except (ValueError, TypeError, AttributeError, KeyError, OSError) as exc:
        backup = path.with_suffix(f".broken-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
        try:
            shutil.copy2(path, backup)
        except OSError as backup_exc:
            raise StorageError(
                f"{path.name} 无法读取且无法备份；停止加载以保留原文件"
            ) from backup_exc
        return (
            default,
            f"{path.name} 无法读取，已保留备份 {backup.name}，本次使用默认值。原因：{exc}",
        )


class ConfigStore:
    def __init__(self, directory: Path):
        self.path = directory / "config.json"

    def load(self) -> tuple[AppConfig, str | None]:
        data, warning = load_json(self.path, AppConfig().to_dict(), AppConfig.from_dict)
        return AppConfig.from_dict(data), warning

    def save(self, config: AppConfig) -> None:
        atomic_json(self.path, config.to_dict())
