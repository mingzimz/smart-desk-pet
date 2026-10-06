from dataclasses import dataclass
from enum import Enum


class Emotion(str, Enum):
    IDLE = "idle"
    HAPPY = "happy"
    ANGRY = "angry"
    SLEEPY = "sleepy"


LABELS = {
    Emotion.IDLE: "悠闲",
    Emotion.HAPPY: "开心",
    Emotion.ANGRY: "生气",
    Emotion.SLEEPY: "困倦",
}


@dataclass
class EmotionMachine:
    mood: float = 55.0
    energy: float = 80.0
    state: Emotion = Emotion.IDLE

    def __post_init__(self) -> None:
        self._resolve()

    def _resolve(self) -> Emotion:
        self.mood = max(0.0, min(100.0, self.mood))
        self.energy = max(0.0, min(100.0, self.energy))
        # Hysteresis prevents flicker around a threshold; sleep has priority.
        if self.energy < 25 or (self.state == Emotion.SLEEPY and self.energy < 40):
            self.state = Emotion.SLEEPY
        elif self.mood < 30 or (self.state == Emotion.ANGRY and self.mood < 40):
            self.state = Emotion.ANGRY
        elif self.mood >= 70 or (self.state == Emotion.HAPPY and self.mood >= 60):
            self.state = Emotion.HAPPY
        else:
            self.state = Emotion.IDLE
        return self.state

    def tick(self, seconds: float) -> Emotion:
        minutes = max(0.0, min(seconds, 300.0)) / 60.0
        drift = min(abs(50.0 - self.mood), minutes * 1.2)
        self.mood += drift if self.mood < 50 else -drift
        self.energy += minutes * (4.0 if self.state == Emotion.SLEEPY else -0.5)
        return self._resolve()

    def pet(self) -> Emotion:
        self.mood += 4
        self.energy -= 1
        return self._resolve()

    def hear(self, text: str) -> Emotion:
        """A replaceable, deliberately small rule engine; not ML sentiment analysis."""
        lowered = text.lower()
        if any(word in lowered for word in ("讨厌", "笨蛋", "生气", "hate")):
            self.mood -= 18
        elif any(word in lowered for word in ("谢谢", "喜欢", "开心", "可爱", "love", "thank")):
            self.mood += 12
        else:
            self.mood += 1
        self.energy -= 2
        if any(word in lowered for word in ("晚安", "困了", "休息", "睡觉")):
            self.energy = min(self.energy, 20)
        return self._resolve()
