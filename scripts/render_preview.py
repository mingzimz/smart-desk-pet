"""Generate a UI preview using the actual Qt widgets, with no remote services."""

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from smart_desktop_pet.controller import PetController  # noqa: E402


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    # Qt's offscreen plugin may not enumerate Windows system fonts.
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "msyh.ttc"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Microsoft YaHei UI", 10))
    output = Path(__file__).resolve().parents[1] / "docs" / "preview.png"
    output.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as data:
        controller = PetController(app, Path(data))
        controller.pet.show()
        controller.show_chat()
        controller.chat.append("你", "今天的程序终于跑起来了，谢谢你陪我！")
        controller.chat.append(
            "桌宠 · 界面展示示例", "你做到了！要不要休息一下，再告诉我最开心的部分？"
        )
        controller.machine.hear("谢谢你，开心")
        controller._sync_view()
        controller.show_settings()
        app.processEvents()
        canvas = QImage(1420, 700, QImage.Format.Format_ARGB32)
        canvas.fill(QColor("#e9edf2"))
        painter = QPainter(canvas)
        for widget, position in (
            (controller.pet, QPoint(30, 180)),
            (controller.chat, QPoint(330, 55)),
            (controller.settings, QPoint(815, 60)),
        ):
            image = widget.grab()
            painter.drawPixmap(position, image)
        painter.end()
        assert canvas.save(str(output))
        controller.shutdown()
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
