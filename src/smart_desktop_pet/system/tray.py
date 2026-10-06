from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayController(QObject):
    toggle_requested = Signal()
    chat_requested = Signal()
    settings_requested = Signal()
    tomato_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(parent)
        self.icon = QSystemTrayIcon(icon, self)
        self.icon.setToolTip("SmartDesktopPet · 你的桌面伙伴")
        self.menu = QMenu()
        self.toggle = self.menu.addAction("隐藏桌宠", self.toggle_requested.emit)
        self.menu.addAction("聊天", self.chat_requested.emit)
        self.menu.addAction("设置", self.settings_requested.emit)
        self.menu.addAction("🍅 番茄钟", self.tomato_requested.emit)
        self.menu.addSeparator()
        self.menu.addAction("退出", self.quit_requested.emit)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)

    @property
    def available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self):
        if self.available:
            self.icon.show()

    def set_visible_label(self, pet_visible: bool):
        self.toggle.setText("隐藏桌宠" if pet_visible else "显示桌宠")

    def _activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.toggle_requested.emit()

    def dispose(self):
        self.icon.hide()
        self.menu.close()
