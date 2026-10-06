from datetime import datetime, timezone
from copy import deepcopy
import json
from pathlib import Path

from ..config.models import number
from ..config.storage import atomic_json, load_json
from ..domain.emotion import EmotionMachine, Emotion


class MemoryStore:
    MAX_TURNS = 20
    MAX_FRAGMENTS = 12
    MAX_BYTES = 4 * 1024 * 1024  # Stay below the JSON reader's 5 MB limit.

    def __init__(self, directory: Path):
        self.path = directory / "memory.json"
        self.data, self.warning = load_json(
            self.path, {"schema_version": 1, "characters": {}}, self._validate
        )

    @classmethod
    def _validate(cls, data: dict) -> None:
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("记忆版本无效")
        profiles = data.get("characters")
        if not isinstance(profiles, dict) or len(profiles) > 200:
            raise ValueError("角色记忆格式无效")
        for profile in profiles.values():
            number(profile["mood"], 0, 100, "心情")
            number(profile["energy"], 0, 100, "精力")
            Emotion(profile.get("state", "idle"))
            turns, fragments = profile["turns"], profile["fragments"]
            if not isinstance(turns, list) or len(turns) > cls.MAX_TURNS:
                raise ValueError("会话记忆过长")
            if not isinstance(fragments, list) or len(fragments) > cls.MAX_FRAGMENTS:
                raise ValueError("记忆片段过长")
            for turn in turns:
                if not isinstance(turn.get("at", ""), str):
                    raise ValueError("对话时间格式无效")
                for key in ("user", "assistant"):
                    if not isinstance(turn[key], str) or len(turn[key]) > 8000:
                        raise ValueError("对话内容格式无效")
            if any(not isinstance(s, str) or len(s) > 500 for s in fragments):
                raise ValueError("记忆片段格式无效")

    def profile(self, character_id: str) -> dict:
        return self.data["characters"].setdefault(
            character_id,
            {"mood": 55.0, "energy": 80.0, "state": "idle", "turns": [], "fragments": []},
        )

    def machine(self, character_id: str) -> EmotionMachine:
        profile = self.profile(character_id)
        return EmotionMachine(
            profile["mood"], profile["energy"], Emotion(profile.get("state", "idle"))
        )

    def checkpoint(self, character_id: str, machine: EmotionMachine) -> None:
        self.profile(character_id).update(
            mood=machine.mood, energy=machine.energy, state=machine.state.value
        )

    def remember(self, character_id: str, user: str, assistant: str, state: Emotion) -> None:
        profile = self.profile(character_id)
        profile["turns"].append(
            {
                "user": user[:8000],
                "assistant": assistant[:8000],
                "emotion": state.value,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        profile["turns"] = profile["turns"][-self.MAX_TURNS :]
        for prefix in ("记住：", "记住:"):
            if user.startswith(prefix):
                fragment = user[len(prefix) :].strip()[:500]
                if fragment and fragment not in profile["fragments"]:
                    profile["fragments"].append(fragment)
                    profile["fragments"] = profile["fragments"][-self.MAX_FRAGMENTS :]

    def clear(self, character_id: str) -> None:
        profile = self.profile(character_id)
        profile["turns"], profile["fragments"] = [], []

    def save(self) -> None:
        self._validate(self.data)
        candidate = deepcopy(self.data)
        size = len(json.dumps(candidate, ensure_ascii=False, indent=2).encode("utf-8"))
        profiles = list(candidate["characters"].values())
        while size > self.MAX_BYTES:
            # Recount near the boundary to avoid dropping a turn that actually fits.
            if size <= self.MAX_BYTES + 65536:
                size = len(json.dumps(candidate, ensure_ascii=False, indent=2).encode("utf-8"))
                if size <= self.MAX_BYTES:
                    break
            with_turns = [profile for profile in profiles if profile["turns"]]
            if with_turns:
                oldest = min(with_turns, key=lambda p: p["turns"][0].get("at", ""))
                removed = oldest["turns"].pop(0)
            else:
                with_fragments = [profile for profile in profiles if profile["fragments"]]
                if not with_fragments:
                    break
                removed = max(with_fragments, key=lambda p: len(p["fragments"]))["fragments"].pop(0)
            # Compact length underestimates removal from indented JSON; safely conservative.
            size -= len(json.dumps(removed, ensure_ascii=False).encode("utf-8"))
        atomic_json(self.path, candidate)
        self.data = candidate
