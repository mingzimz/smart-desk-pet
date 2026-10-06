from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget
from PySide6.QtCore import Signal
from pathlib import Path


class PetWindow(QWidget):
    clicked = Signal()
    chat_requested = Signal()
    drop_received = Signal(str, str)
    settings_requested = Signal()
    tomato_requested = Signal()
    hide_requested = Signal()
    quit_requested = Signal()
    moved = Signal()
    visibility_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartDesktopPet")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(280, 310)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("单击摸摸并聊天 · 拖动移动 · 右键打开菜单")
        self.frame = QPixmap()
        self.caption = "小团 · 悠闲"
        self.press_global: QPoint | None = None
        self.press_window = QPoint()
        self.dragging = False
        self.menu = QMenu(self)
        for title, signal in (
            ("聊天", self.chat_requested),
            ("设置", self.settings_requested),
            ("🍅 番茄钟", self.tomato_requested),
            ("隐藏", self.hide_requested),
            ("退出", self.quit_requested),
        ):
            self.menu.addAction(title, signal.emit)
        self.setAcceptDrops(True)

    def set_frame(self, frame: QPixmap) -> None:
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.frame.isNull():
            target = self.frame.size().scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio)
            rect = QRectF(
                (280 - target.width()) / 2,
                (280 - target.height()) / 2,
                target.width(),
                target.height(),
            )
            painter.drawPixmap(rect, self.frame, QRectF(self.frame.rect()))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(39, 43, 54, 210))
        painter.drawRoundedRect(QRectF(24, 278, 232, 26), 13, 13)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(28, 278, 224, 26), Qt.AlignmentFlag.AlignCenter, self.caption)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_global = event.globalPosition().toPoint()
            self.press_window = self.pos()
            self.dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.press_global is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.press_global
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
            if self.dragging:
                self.move(self.press_window + delta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.press_global is not None:
            self.press_global = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self.dragging:
                self.clamp_to_screen()
                self.moved.emit()
            else:
                self.clicked.emit()

    def clamp_to_screen(self):
        screen = (
            QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        )
        if screen:
            area = screen.availableGeometry()
            self.move(
                max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                max(area.top(), min(self.y(), area.bottom() - self.height() + 1)),
            )

    def contextMenuEvent(self, event):
        self.menu.popup(event.globalPos())

    def showEvent(self, event):
        self.visibility_changed.emit(True)
        super().showEvent(event)

    def hideEvent(self, event):
        self.visibility_changed.emit(False)
        super().hideEvent(event)

    def closeEvent(self, event):
        event.ignore()
        self.hide_requested.emit()
    def dragEnterEvent(self, event):
        # 只接受文本、文件类型的拖拽
        mime = event.mimeData()
        if mime.hasText() or mime.hasUrls():
            event.acceptProposedAction()  # 显示可拖拽的光标效果
        else:
            event.ignore()

    def dropEvent(self, event):
        mime = event.mimeData()

        # 优先级1：先判断是不是文件拖拽（必须放在最前面）
        if mime.hasUrls():
            url = mime.urls()[0]
            if not url.isLocalFile():
                event.ignore()
                return
            file_path = url.toLocalFile()
            suffix = Path(file_path).suffix.lower()

            if suffix in (".py", ".java", ".cpp", ".c", ".js"):
                self.drop_received.emit("code_file", file_path)
            elif suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                self.drop_received.emit("image_file", file_path)
            else:
                self.drop_received.emit("file", file_path)

        # 优先级2：再判断是不是纯文本拖拽
        elif mime.hasText():
            text = mime.text().strip()
            self.drop_received.emit("text", text)

        else:
            event.ignore()
            return

        event.acceptProposedAction()


