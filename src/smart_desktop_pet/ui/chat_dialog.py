from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from .theme import STYLE


class ChatDialog(QDialog):
    send_requested = Signal(str)
    cancel_requested = Signal()
    settings_requested = Signal()
    clear_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("和桌宠聊聊 · SmartDesktopPet")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.resize(460, 590)
        self.setMinimumSize(380, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        self.title = QLabel("和小团聊聊")
        self.title.setObjectName("title")
        layout.addWidget(self.title)
        self.status = QLabel("离线演示 · 悠闲")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.history = QTextBrowser()
        self.history.setOpenExternalLinks(False)
        layout.addWidget(self.history, 1)
        hint = QLabel("输入“记住：我喜欢猫”保存记忆片段。模型会收到当前角色的近期对话与记忆。")
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)
        self.input = QLineEdit()
        self.input.setPlaceholderText("想和我说点什么？")
        self.input.setMaxLength(2000)
        self.input.returnPressed.connect(self._send)
        layout.addWidget(self.input)
        row = QHBoxLayout()
        settings = QPushButton("设置")
        settings.setAutoDefault(False)
        settings.clicked.connect(self.settings_requested.emit)
        self.clear = QPushButton("清除记忆")
        self.clear.clicked.connect(self.clear_requested.emit)
        self.cancel = QPushButton("取消")
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self.cancel_requested.emit)
        self.send = QPushButton("发送")
        self.send.setDefault(True)  # 新增这行
        self.send.setObjectName("primary")
        self.send.clicked.connect(self._send)
        for widget in (settings, self.clear, self.cancel, self.send):
            row.addWidget(widget)
        layout.addLayout(row)

    def _send(self):
        text = self.input.text().strip()
        if text and self.send.isEnabled():
            self.send_requested.emit(text)

    def append(self, author: str, text: str) -> None:
        cursor = self.history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Always insert plain text. User/model output must never be parsed as HTML.
        cursor.insertText(f"{author}\n{text}\n\n")
        self.history.setTextCursor(cursor)
        self.history.ensureCursorVisible()

    def load_history(self, name: str, turns: list[dict]) -> None:
        self.title.setText("和" + name.split(" · ")[-1] + "聊聊")
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.history.clear()
        for turn in turns:
            self.append("你", turn["user"])
            self.append("桌宠", turn["assistant"])
        if not turns:
            self.append("桌宠", "我在这里，随时可以聊聊。")

    def set_busy(self, busy: bool) -> None:
        self.send.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.clear.setEnabled(not busy)
        self.cancel.setEnabled(busy)
        self.send.setText("等待回复…" if busy else "发送")
