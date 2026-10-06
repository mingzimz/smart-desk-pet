"""Composition root: coordinates modules without putting business logic in widgets."""

from copy import deepcopy
import os
from pathlib import Path
import time
from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox,QLabel
from .ai.client import ChatClient
from .ai.context import build_messages
from .characters.catalog import CharacterCatalog
from .config.models import AppConfig
from .config.storage import ConfigStore, StorageError
from .domain.emotion import LABELS
from .memory.store import MemoryStore
from .rendering.animator import Animator
from .rendering.pet_window import PetWindow
from .system.tray import TrayController
from .ui.chat_dialog import ChatDialog
from .ui.settings_dialog import SettingsDialog
from .system.tomato_timer import TomatoTimer
from .ui.tomato_dialog import TomatoDialog
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
import random
import re
import json
from datetime import datetime, timedelta
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel
import importlib.util
from .plugins.plugin_base import PluginBase

class PetController(QObject):
    def __init__(self, application: QApplication, directory: Path, demo: bool = False):
        super().__init__(application)
        self.application = application
        self.directory = directory
        self.config_store = ConfigStore(directory)
        self.config, warning = self.config_store.load()
        if demo:
            self.config.provider = "demo"
        self.memory = MemoryStore(directory)
        self.catalog = CharacterCatalog(directory)
        self.characters = self.catalog.list()
        self.warnings = [
            item for item in [warning, self.memory.warning, *self.catalog.warnings] if item
        ]
        self.character = next(
            (c for c in self.characters if c.id == self.config.character_id), None
        )
        if self.character is None:
            self.warnings.append("上次使用的角色不存在，已切换为奶油猫。原角色记忆仍保留。")
            self.character = self.characters[0]
        try:
            pack = self.catalog.load(self.character)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            self.warnings.append("角色动画无法加载，已切换为奶油猫。请检查角色包。")
            self.character = self.characters[0]
            pack = self.catalog.load(self.character)
        self.config.character_id = self.character.id
        self.machine = self.memory.machine(self.character.id)
        self.pet = PetWindow()
        self.chat = ChatDialog()
        self.settings: SettingsDialog | None = None
        self.animator = Animator(self)
        self.animator.frame_changed.connect(self.pet.set_frame)
        self.animator.load(pack)
        icon = QIcon(QPixmap.fromImage(pack.frames[self.machine.state][0]))
        self.application.setWindowIcon(icon)
        self.tray = TrayController(icon, self)
        self.client = ChatClient(self)
        self.session_key = ""
        self.pending_user: str | None = None
        self.last_tick = time.monotonic()
        self.last_time_msg = 0  # 记录上次说时间台词的时间戳，控制发言间
        self.storage_warning_shown = False
        self.stopping = False
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self._tick)
        self.save_timer = QTimer(self)
        self.save_timer.setInterval(30000)
        self.save_timer.timeout.connect(self._autosave)
        self.pet.clicked.connect(self._pet_clicked)
        self.pet.drop_received.connect(self._on_drop_received)
        self.pet.chat_requested.connect(self.show_chat)
        self.pet.settings_requested.connect(self.show_settings)
        self.pet.tomato_requested.connect(self.open_tomato_dialog)
        self.pet.hide_requested.connect(self.toggle_pet)
        self.pet.quit_requested.connect(self.quit)
        self.pet.moved.connect(self._save_position)
        self.pet.moved.connect(self._update_bubble_position)
        self.pet.visibility_changed.connect(self.animator.set_active)
        self.pet.visibility_changed.connect(self.tray.set_visible_label)
        self.tray.toggle_requested.connect(self.toggle_pet)
        self.tray.chat_requested.connect(self.show_chat)
        self.tray.settings_requested.connect(self.show_settings)
        self.tray.tomato_requested.connect(self.open_tomato_dialog)
        self.tray.quit_requested.connect(self.quit)
        self.chat.send_requested.connect(self.send)
        self.chat.cancel_requested.connect(self.cancel)
        self.chat.settings_requested.connect(self.show_settings)
        self.chat.clear_requested.connect(self.clear_memory)
        self.client.succeeded.connect(self._received)
        self.client.failed.connect(self._failed)
        self.client.busy_changed.connect(self.chat.set_busy)
        self.application.aboutToQuit.connect(self.shutdown)
        self.reminders = []  # 待触发提醒列表：[{"time": datetime, "content": "内容"}]
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start(1000)  # 每秒检查一次
        self.reminder_parsing = False  # 当前AI请求是否用于解析提醒
        self._pending_reminder_text = ""  # 暂存用户原始输入，解析失败时降级用
                # ========== 插件系统启动 ==========
        self.plugins = {}  # 存放所有已加载插件
        self._load_all_plugins()


        self._reload_history()
        self._sync_view()
        if self.config.position:
            self.pet.move(*self.config.position)
        else:
            area = self.application.primaryScreen().availableGeometry()
            self.pet.move(
                area.right() - self.pet.width() - 24, area.bottom() - self.pet.height() - 24
            )
        self.pet.clamp_to_screen()
        self.tomato_timer = TomatoTimer()
        self.tomato_dialog = TomatoDialog(self.tomato_timer)
        self._tomato_audio = QAudioOutput()
        self._tomato_player = QMediaPlayer()
        self._tomato_player.setAudioOutput(self._tomato_audio)
        self._tomato_audio.setVolume(0.8)
        sound_path = Path(__file__).parent / "assets" / "relax.ogg"
        self._tomato_player.setSource(QUrl.fromLocalFile(str(sound_path.resolve())))
        # 番茄结束回调，触发桌宠气泡
        self.tomato_timer.finished_signal.connect(self.on_tomato_finish)
                # 头顶提醒气泡
        self.reminder_bubble = QLabel()
        self.reminder_bubble.setWindowFlags(
            Qt.WindowType.Tool | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.NoDropShadowWindowHint
        )
        self.reminder_bubble.setStyleSheet("""
            QLabel {
                /* 黄色背景 */
                background-color: #fff3cd;
                /* 深黄色细边框，轮廓更清晰 */
                border: 1px solid #ffe066;
                /* 圆角设为0，纯矩形 */
                border-radius: 1px;
                /* 内边距，文字不贴边 */
                padding: 10px 18px;
                /* 黑色加粗文字 */
                color: #000000;
                font-weight: bold;
                font-size: 16px;
                font-family: "Microsoft YaHei", sans-serif;
            }
        """)

        self.reminder_bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reminder_bubble.setWordWrap(True)
        self.reminder_bubble.setMaximumWidth(280)
        self.reminder_bubble.hide()
        # 气泡自动消失定时器
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.reminder_bubble.hide)



    def start(self, tray: bool = True):
        self.pet.show()
        if tray:
            self.tray.show()
        self.tick_timer.start()
        self.save_timer.start()
        if self.warnings:
            QTimer.singleShot(0, self._show_warnings)

    def _show_warnings(self):
        QMessageBox.warning(self.pet, "数据加载提示", "\n\n".join(self.warnings))

    def _reload_history(self):
        self.chat.load_history(self.character.name, self.memory.profile(self.character.id)["turns"])

    def _sync_view(self):
        self.animator.configure(self.machine.state, self.config.animation_speed)
        self.pet.setWindowOpacity(self.config.opacity)
        name = self.character.name.split(" · ")[-1]
        self.pet.caption = f"{name[:14]} · {LABELS[self.machine.state]}"
        mode = {"demo": "离线演示", "ollama": "Ollama", "openai": "兼容 API"}[self.config.provider]
        self.chat.status.setText(
            f"{mode} · {LABELS[self.machine.state]}  |  心情 {self.machine.mood:.0f} / 精力 {self.machine.energy:.0f}"
        )
        self.pet.update()

    def _tick(self):
        now = time.monotonic()
        self.machine.tick(now - self.last_tick)
        self.last_tick = now
        self._time_chat()
        self._sync_view()

    def _pet_clicked(self):
        self.machine.pet()
        self._sync_view()
        self.show_chat()

    def show_chat(self):
        if not self.chat.isVisible():
            screen = (
                self.application.screenAt(self.pet.frameGeometry().center())
                or self.application.primaryScreen()
            )
            area = screen.availableGeometry()
            self.chat.move(
                max(
                    area.left(),
                    min(self.pet.x() - self.chat.width(), area.right() - self.chat.width() + 1),
                ),
                max(area.top(), min(self.pet.y(), area.bottom() - self.chat.height() + 1)),
            )
        self.chat.show()
        self.chat.raise_()
        self.chat.activateWindow()
        self.chat.input.setFocus()

    def toggle_pet(self):
        if self.pet.isVisible():
            if not self.tray.available:
                QMessageBox.information(
                    self.pet,
                    "托盘不可用",
                    "当前系统托盘不可用，桌宠保持显示。可以在右键菜单中退出。",
                )
                return
            self.pet.hide()
        else:
            self.pet.clamp_to_screen()
            self.pet.show()

    def show_settings(self):
        if self.settings and self.settings.isVisible():
            self.settings.raise_()
            self.settings.activateWindow()
            return
        if self.settings:
            self.settings.deleteLater()
        self.characters = self.catalog.list()
        self.settings = SettingsDialog(
            self.config, self.characters, str(self.directory), self.session_key
        )
        self.settings.apply_requested.connect(self.apply_settings)
        self.settings.import_requested.connect(self.import_character)
        self.settings.show()

    def apply_settings(self, candidate: AppConfig, session_key: str):
        try:
            candidate.validate()
            characters = self.catalog.list()
            character = next((c for c in characters if c.id == candidate.character_id), None)
            if not character:
                raise ValueError("角色不存在，请重新选择")
            pack = self.catalog.load(character)
            # Persist before changing running state so a failed save leaves it intact.
            candidate.position = [self.pet.x(), self.pet.y()]
            self.config_store.save(candidate)
        except (StorageError, ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
            QMessageBox.warning(self.settings, "无法应用设置", str(exc))
            return
        self.cancel(announce=False)
        previous_id = self.character.id
        self.memory.checkpoint(previous_id, self.machine)
        self.config, self.character, self.session_key = candidate, character, session_key
        if previous_id != character.id:
            self.machine = self.memory.machine(character.id)
        self.animator.load(pack)
        self._reload_history()
        self._sync_view()
        self._autosave()
        if self.settings:
            self.settings.accept()

    def import_character(self):
        filename, _ = QFileDialog.getOpenFileName(
            self.settings, "选择角色图片", "", "图片 (*.png *.jpg *.jpeg *.webp)"
        )
        if not filename:
            return
        name, accepted = QInputDialog.getText(
            self.settings, "给角色起个名字", "角色名称", text=Path(filename).stem[:60]
        )
        if not accepted:
            return
        try:
            character = self.catalog.import_image(Path(filename), name)
            self.settings.add_character(character)
        except (ValueError, OSError, StorageError) as exc:
            QMessageBox.warning(self.settings, "导入失败", str(exc))

    def send(self, text: str):
        # 先尝试用AI解析自然语言提醒
        if self._try_parse_reminder_ai(text):
            # 已发起AI解析，后续走回调，直接返回
            return
        if self.client.busy or not text.strip():
            return
        text = text.strip()[:2000]
        profile = self.memory.profile(self.character.id)
        # Preview the emotion for prompting; commit only after a successful response.
        preview = deepcopy(self.machine)
        preview.hear(text)
        messages = build_messages(self.config.persona, profile, preview, text)
        self.pending_user = text
        self.chat.append("你", text)
        key = self.session_key or os.environ.get(self.config.api_key_env, "")
        self.client.send(self.config, messages, key)

    def _received(self, answer: str):
        # ===== 新增：提醒解析分支 =====
        if self.reminder_parsing:
            self.reminder_parsing = False  # 立刻关闭标记
            self._handle_reminder_parse_result(answer)
            return  # 不进入正常聊天显示逻辑
        if self.pending_user is None:
            return
        user, self.pending_user = self.pending_user, None
        self.machine.hear(user)
        self.memory.remember(self.character.id, user, answer, self.machine.state)
        self.chat.append("桌宠", answer)
        self.chat.input.clear()
        self.chat.input.setFocus()
        self._sync_view()
        self._autosave()

    def _failed(self, message: str):
        # 如果是提醒解析时失败，清除标记并提示
        if self.reminder_parsing:
            self.reminder_parsing = False
            self.chat.append("桌宠", "提醒解析失败啦，换个说法试试？")
            return
        self.pending_user = None
        self.chat.append("连接提示", message + "。本次对话未写入记忆，输入已保留。")
        self.chat.input.setFocus()

    def cancel(self, announce: bool = True):
        was_busy = self.client.busy
        self.pending_user = None
        self.client.cancel()
        if announce and was_busy:
            self.chat.append("提示", "请求已取消，本次对话未写入记忆。")

    def clear_memory(self):
        if self.client.busy:
            return
        result = QMessageBox.question(
            self.chat, "清除当前角色记忆", "删除当前角色的近期对话和记忆片段？人设与情绪值会保留。"
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        before = deepcopy(self.memory.data)
        self.memory.clear(self.character.id)
        try:
            self.memory.save()
        except StorageError as exc:
            self.memory.data = before
            QMessageBox.warning(self.chat, "清除失败", str(exc))
            return
        self._reload_history()

    def _save_position(self):
        self.config.position = [self.pet.x(), self.pet.y()]
        self._autosave()

    def _autosave(self):
        self.memory.checkpoint(self.character.id, self.machine)
        self.config.position = [self.pet.x(), self.pet.y()]
        try:
            self.config_store.save(self.config)
            self.memory.save()
            self.storage_warning_shown = False
        except StorageError as exc:
            if not self.storage_warning_shown:
                self.storage_warning_shown = True
                QMessageBox.warning(
                    self.chat if self.chat.isVisible() else self.pet, "保存失败", str(exc)
                )

    def shutdown(self):
        if self.stopping:
            return
        self.stopping = True
        self.tick_timer.stop()
        self.save_timer.stop()
        self.client.cancel()
        self.animator.set_active(False)
        self._autosave()
        self.tray.dispose()
        self.pet.hide()
        self.chat.hide()
        if self.settings:
            self.settings.hide()

    def quit(self):
        self.shutdown()
        self.application.quit()
    def open_tomato_dialog(self):
        self.tomato_dialog.show()
        self.tomato_dialog.raise_()

    def on_tomato_finish(self, phase: str):
        print("=== 触发结束回调,phase =", phase)
        self._tomato_player.setPosition(0)
        self._tomato_player.play()
        if phase == "work":
            self.chat.append("番茄钟", "🍅 工作结束！该休息一会啦")
        else:
            self.chat.append("番茄钟", "☕ 休息结束，继续专注！")
    def _time_chat(self):
        now = time.monotonic()
        # 发言间隔：至少6分钟（360秒）说一次，避免太频繁打扰
        if now - self.last_time_msg < 360:
            return
        hour = datetime.now().hour
        msg = None
        if 7 <= hour < 9:
            msg = random.choice(["早呀，今天也要加油哦~", "新的一天开始啦！", "早饭吃了吗？"])
        elif 12 <= hour < 14:
            msg = random.choice(["中午吃什么呀？", "干饭时间到！", "午休一会吧~"])
        elif 14 <= hour < 16:
            msg = random.choice(["好困啊...", "下午容易摸鱼哦", "要不要喝杯咖啡？"])
        elif 16 <= hour < 19:
            msg = random.choice(["有点饿...", "晚上吃什么呢", "红烧肉怎么样"])
        elif hour >= 23 or hour < 5:
            msg = random.choice(["还不睡呀？", "熬夜对身体不好哦", "忙完就早点休息吧"])
        # 匹配到时间段就发送
        if msg:
            self.chat.append("桌宠", msg)
            self.last_time_msg = now
    def _on_drop_received(self, drop_type: str, content: str):
        if drop_type == "text":
            # 拖拽纯文本：让AI总结内容
            prompt = f"帮我用一两句话简短总结这段内容：\n{content[:1000]}"
            # 直接走正常聊天的完整发送流程
            self.send(prompt)

        elif drop_type == "code_file":
            # 拖拽代码文件：读取后让AI点评
            try:
                with open(content, 'r', encoding='utf-8') as f:
                    code_content = f.read()
                prompt = f"简单调侃点评一下这段代码，不用太严肃：\n{code_content[:1000]}"
                self.send(prompt)
            except Exception:
                self.chat_dialog.append("桌宠", "这个文件我打不开呀~")

        elif drop_type == "image_file":
            file_name = Path(content).name
            self.chat_dialog.append("桌宠", f"这张 {file_name} 看起来好有意思！")

        elif drop_type == "file":
            file_name = Path(content).name
            self.chat_dialog.append("桌宠", f"收到投喂：{file_name} ✨")
    def _try_parse_reminder_ai(self, user_text: str) -> bool:
        """
        尝试用AI解析自然语言提醒
        返回True表示已发起AI请求，后续走回调；返回False表示不处理
        """
        # 简单预判：只有包含"提醒"关键词才发起AI解析，减少无效调用
        if "提醒" not in user_text:
            return False

        # 构造严格的解析Prompt，强制AI只返回JSON
        prompt = f"""你是一个时间提醒解析器。请从用户的话中提取提醒时间和提醒内容，只返回标准JSON，不要任何多余文字、解释、代码块。
JSON必须包含两个字段：
- minutes: 整数，距离当前时间还有多少分钟触发提醒
- content: 字符串，提醒的具体内容

如果用户的话里没有明确的提醒时间，或者不是提醒请求，就返回：{{"error": "无法识别"}}

用户的原话：{user_text}"""

        # 调用AI客户端发起请求（参数格式和你项目原生完全一致）
        messages = [{"role": "user", "content": prompt}]
        key = self.session_key or os.environ.get(self.config.api_key_env, "")
        self.client.send(self.config, messages, key)

        # 打上解析标记，暂存原始文本
        self.reminder_parsing = True
        self._pending_reminder_text = user_text
        return True
    def _handle_reminder_parse_result(self, answer: str):
        """处理AI返回的提醒解析结果，带容错提取"""
        try:
            # 用正则提取JSON部分，过滤掉模型返回的多余解释文字
            json_match = re.search(r'\{[\s\S]*\}', answer)
            if not json_match:
                self.chat.append("桌宠", "抱歉，我没理解你的提醒时间，请换个说法试试~")
                return
            
            data = json.loads(json_match.group())
            
            if "error" in data:
                self.chat.append("桌宠", "抱歉，我没识别出明确的提醒时间，请说明具体的分钟数~")
                return

            minutes = int(data.get("minutes", 0))
            content = data.get("content", "提醒事项")

            if minutes <= 0:
                self.chat.append("桌宠", "提醒时间需要大于0分钟哦~")
                return

            # 计算触发时间，加入提醒队列
            trigger_time = datetime.now() + timedelta(minutes=minutes)
            self.reminders.append({
                "time": trigger_time,
                "content": content
            })

            self.chat.append("桌宠", f"好的，我会在{minutes}分钟后提醒你：{content}")

        except Exception as e:
            self.chat.append("桌宠", "设置提醒失败了，请换一种表述试试~")
            print(f"提醒解析错误: {e}")

    def _check_reminders(self):
        """每秒检查一次，触发到期的提醒"""
        now = datetime.now()
        # 倒序遍历，方便直接移除已触发项
        for i in range(len(self.reminders) - 1, -1, -1):
            reminder = self.reminders[i]
            if now >= reminder["time"]:
                self._trigger_reminder(reminder["content"])
                self.reminders.pop(i)

    def _trigger_reminder(self, content: str):
       """触发提醒：聊天窗口留痕 + 桌宠头顶气泡"""
        # 1. 聊天窗口留痕（保留历史记录）
       self.chat.append("桌宠", f"🔔 提醒时间到啦：{content}")
        # 2. 桌宠头顶气泡显示
       self.reminder_bubble.setText(f"奶娃提醒您： {content}")
       self.reminder_bubble.adjustSize()  # 自适应文字大小
       self._update_bubble_position()
       self.reminder_bubble.show()
       self.reminder_bubble.raise_()  # 置顶
       self.bubble_timer.start(30000)
    def _update_bubble_position(self):
        """更新气泡位置到桌宠窗口正上方，水平居中+屏幕边界保护"""
        pet_geometry = self.pet.geometry()
        bubble_width = self.reminder_bubble.width()
        bubble_height = self.reminder_bubble.height()
        
        # 水平居中对齐桌宠
        x = pet_geometry.x() + (pet_geometry.width() - bubble_width) // 2
        # 防止气泡超出屏幕左右边缘
        screen_width = self.application.primaryScreen().availableGeometry().width()
        x = max(0, min(x, screen_width - bubble_width))
        
        # 垂直显示在桌宠头顶上方
        y = pet_geometry.y() - bubble_height - 6
        # 防止气泡超出屏幕上边缘
        y = max(0, y)
        
        self.reminder_bubble.move(x, y)
    def _load_all_plugins(self):
        """自动扫描 plugins 目录，加载所有 *_plugin.py 文件"""
        plugins_dir = Path(__file__).parent / "plugins"
        if not plugins_dir.exists():
            print("[插件系统] 目录不存在，跳过加载")
            return

        for file in plugins_dir.glob("*_plugin.py"):
            try:
                # 完整包名：和项目包结构对应，让插件内的相对导入生效
                module_full_name = f"smart_desktop_pet.plugins.{file.stem}"
                
                # 三步导入都放在 try 内，避免变量未定义
                spec = importlib.util.spec_from_file_location(module_full_name, file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找插件类并实例化
                for attr_name in dir(module):
                    cls = getattr(module, attr_name)
                    if (isinstance(cls, type) and 
                        issubclass(cls, PluginBase) and 
                        cls is not PluginBase):
                        plugin = cls(self)
                        plugin.on_load()
                        self.plugins[plugin.plugin_id] = plugin
                        print(f"[插件加载成功] {plugin.plugin_name}")
                        
            except Exception as e:
                print(f"[插件加载失败] {file.name}: {str(e)}")





