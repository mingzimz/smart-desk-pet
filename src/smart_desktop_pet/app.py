import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from .config.storage import data_directory
from .controller import PetController


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SmartDesktopPet — Windows 智能桌宠")
    parser.add_argument(
        "--data-dir", type=Path, help="独立的数据目录（默认 %%APPDATA%%/SmartDesktopPet）"
    )
    parser.add_argument("--demo", action="store_true", help="使用无需模型的离线演示模式")
    args = parser.parse_args(argv)
    application = QApplication([sys.argv[0]])
    application.setApplicationName("SmartDesktopPet")
    application.setOrganizationName("SmartDesktopPet")
    application.setQuitOnLastWindowClosed(False)
    directory = args.data_dir.resolve() if args.data_dir else data_directory()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(directory / "app.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(100):
            QMessageBox.information(
                None,
                "SmartDesktopPet",
                "此数据目录已有桌宠运行，或目录不可写。请检查系统托盘与目录权限。",
            )
            return 1
        handler = RotatingFileHandler(
            directory / "app.log", maxBytes=512000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger = logging.getLogger("smart_desktop_pet")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.info("Application starting")

        def exception_hook(exc_type, value, traceback):
            logger.error("Unhandled error", exc_info=(exc_type, value, traceback))
            QMessageBox.critical(None, "发生错误", "应用遇到异常，详情已保存至数据目录的 app.log。")

        sys.excepthook = exception_hook
        controller = PetController(application, directory, args.demo)
        controller.start()
        result = application.exec()
        lock.unlock()
        handler.close()
        logger.removeHandler(handler)
        return result
    except Exception as exc:
        QMessageBox.critical(None, "无法启动", f"SmartDesktopPet 无法初始化：{exc}")
        return 1
