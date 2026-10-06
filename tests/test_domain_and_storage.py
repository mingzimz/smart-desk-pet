from copy import deepcopy
import json

import pytest

from smart_desktop_pet.ai.context import build_messages
from smart_desktop_pet.config.models import AppConfig
from smart_desktop_pet.config.storage import ConfigStore, StorageError
from smart_desktop_pet.domain.emotion import Emotion, EmotionMachine
from smart_desktop_pet.memory.store import MemoryStore


def test_sleep_priority_recovery_and_hysteresis():
    machine = EmotionMachine(mood=90, energy=20)
    assert machine.state == Emotion.SLEEPY
    machine.tick(240)
    assert machine.energy == 36
    assert machine.state == Emotion.SLEEPY
    machine.tick(60)
    assert machine.state == Emotion.HAPPY
    machine.mood = 65
    machine.tick(1)
    assert machine.state == Emotion.HAPPY
    machine.mood = 59
    machine.tick(1)
    assert machine.state == Emotion.IDLE


def test_dialog_and_click_change_emotion_with_bounds():
    machine = EmotionMachine()
    for _ in range(100):
        machine.pet()
    assert machine.mood == 100
    assert machine.energy == 0
    assert machine.state == Emotion.SLEEPY
    machine = EmotionMachine()
    machine.hear("谢谢你，我很喜欢你")
    assert machine.mood == 67
    machine.hear("谢谢")
    assert machine.state == Emotion.HAPPY
    machine.hear("晚安")
    assert machine.state == Emotion.SLEEPY
    machine = EmotionMachine(mood=40)
    machine.hear("笨蛋")
    assert machine.state == Emotion.ANGRY


@pytest.mark.parametrize(
    "key,value",
    [
        ("opacity", 0),
        ("animation_speed", float("nan")),
        ("timeout_seconds", True),
        ("base_url", "file:///secret"),
        ("base_url", "https://user:secret@example.com"),
        ("base_url", "https://example.com/?key=secret"),
        ("position", [1]),
        ("schema_version", 999),
        ("personas", {"a": ""}),
        ("character_id", "../escape"),
    ],
)
def test_config_rejects_invalid_values(key, value):
    config = AppConfig()
    setattr(config, key, value)
    with pytest.raises(ValueError):
        config.validate()


def test_config_roundtrip_and_corruption_backup(tmp_path):
    store = ConfigStore(tmp_path)
    config = AppConfig()
    config.personas["builtin-cat"] = "我是中文桌宠"
    config.position = [-1200, 40]
    store.save(config)
    loaded, warning = store.load()
    assert loaded == config
    assert warning is None
    store.path.write_text("{broken", encoding="utf-8")
    loaded, warning = store.load()
    assert loaded == AppConfig()
    assert warning
    assert next(tmp_path.glob("*.broken-*.json")).read_text() == "{broken"


def test_atomic_failure_preserves_existing_file(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path)
    store.save(AppConfig())
    original = store.path.read_bytes()

    def failure(*args):
        raise PermissionError("simulated locked file")

    monkeypatch.setattr("smart_desktop_pet.config.storage.os.replace", failure)
    with pytest.raises(StorageError):
        store.save(AppConfig(model="different"))
    assert store.path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_character_memory_isolated_bounded_and_restored(tmp_path):
    memory = MemoryStore(tmp_path)
    for index in range(30):
        memory.remember("cat", f"记住：偏好{index}", "好的", Emotion.HAPPY)
    memory.checkpoint("cat", EmotionMachine(80, 55))
    memory.profile("rabbit")
    memory.save()
    restored = MemoryStore(tmp_path)
    assert len(restored.profile("cat")["turns"]) == 20
    assert len(restored.profile("cat")["fragments"]) == 12
    assert restored.profile("rabbit")["turns"] == []
    assert restored.machine("cat").mood == 80
    assert restored.machine("cat").state == Emotion.HAPPY
    restored.clear("cat")
    restored.save()
    assert MemoryStore(tmp_path).profile("cat")["fragments"] == []


def test_corrupt_memory_is_backed_up(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(json.dumps({"schema_version": 1, "characters": {"cat": {"mood": "bad"}}}))
    memory = MemoryStore(tmp_path)
    assert memory.warning
    assert memory.data["characters"] == {}
    assert list(tmp_path.glob("memory.broken-*.json"))


def test_context_uses_character_persona_pairs_and_budget(tmp_path):
    memory = MemoryStore(tmp_path)
    for index in range(20):
        memory.remember("cat", f"user-{index}" + "x" * 1500, "y" * 1500, Emotion.IDLE)
    profile = memory.profile("cat")
    profile["fragments"] = ["我喜欢猫"]
    before = deepcopy(profile)
    messages = build_messages("你是小团", profile, EmotionMachine(), "你好")
    assert "你是小团" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "你好"}
    assert sum(len(message["content"]) for message in messages) <= 16000
    assert messages[1]["role"] == "user"
    assert "我喜欢猫" in messages[1]["content"]
    assert profile == before


def test_global_memory_budget_keeps_saved_file_reloadable(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.MAX_BYTES = 3000
    for index in range(8):
        memory.remember("cat", "中文" * 200, "回复" * 200, Emotion.IDLE)
    memory.save()
    assert memory.path.stat().st_size <= memory.MAX_BYTES
    restored = MemoryStore(tmp_path)
    assert restored.warning is None
    assert restored.profile("cat")["turns"]
    assert len(restored.profile("cat")["turns"]) < 8
