from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

from ..characters.catalog import AnimationPack
from ..domain.emotion import Emotion


class Animator(QObject):
    frame_changed = Signal(QPixmap)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = Emotion.IDLE
        self.speed = 1.0
        self.index = 0
        self.frames = {}
        self.fps = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)

    def load(self, pack: AnimationPack) -> None:
        self.frames = {
            state: [QPixmap.fromImage(frame) for frame in images]
            for state, images in pack.frames.items()
        }
        self.fps = pack.fps
        self.index = 0
        self.refresh()

    def configure(self, state: Emotion, speed: float) -> None:
        if self.state != state:
            self.index = 0
        self.state, self.speed = state, speed
        self.refresh()

    def refresh(self) -> None:
        if self.frames:
            self.timer.setInterval(max(16, round(1000 / (self.fps[self.state] * self.speed))))
            self.frame_changed.emit(
                self.frames[self.state][self.index % len(self.frames[self.state])]
            )

    def set_active(self, active: bool) -> None:
        self.timer.start() if active else self.timer.stop()

    def advance(self) -> None:
        if self.frames:
            self.index = (self.index + 1) % len(self.frames[self.state])
            self.frame_changed.emit(self.frames[self.state][self.index])
