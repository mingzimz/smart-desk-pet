from .plugin_base import PluginBase
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, QTime, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from pathlib import Path
import json
from datetime import datetime
from PySide6.QtGui import QAction



class SchedulePlugin(PluginBase):
    plugin_id = "schedule"
    plugin_name = "课程表提醒"
    plugin_desc = "周课表管理，上课前自动弹窗提醒"

    def on_load(self):
        self._load_schedule()
        self._init_bubble()
        self._init_audio()
        
        # 每分钟检查一次课程
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self._check_class)
        self.check_timer.start(60 * 1000)
        
        self._reminded_today = set()
        self._bind_entry()

    # ===== 数据持久化 =====
    def _get_data_path(self):
        return self.controller.directory / "schedule.json"

    def _load_schedule(self):
        path = self._get_data_path()
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.schedule_list = json.load(f)
        else:
            self.schedule_list = []

    def _save_schedule(self):
        with open(self._get_data_path(), 'w', encoding='utf-8') as f:
            json.dump(self.schedule_list, f, ensure_ascii=False, indent=2)

    # ===== 气泡+音效（和你原有样式一致）=====
    def _init_bubble(self):
        self.reminder_bubble = QLabel()
        self.reminder_bubble.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.reminder_bubble.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffe066;
                border-radius: 0px;
                padding: 10px 18px;
                color: #000;
                font-weight: bold;
                font-size: 15px;
                font-family: "Microsoft YaHei", sans-serif;
            }
        """)
        self.reminder_bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reminder_bubble.setWordWrap(True)
        self.reminder_bubble.setMaximumWidth(300)
        self.reminder_bubble.hide()

        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.reminder_bubble.hide)

    def _init_audio(self):
        self._audio = QAudioOutput()
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(0.7)
        # 复用你现有的提醒音效，路径不对自行调整
        sound_path = Path(__file__).parent.parent / "assets" / "relax.ogg"
        self._player.setSource(QUrl.fromLocalFile(str(sound_path.resolve())))

    def _show_bubble(self, text):
        self.reminder_bubble.setText(text)
        self.reminder_bubble.adjustSize()

        # 定位到桌宠头顶
        pet_geo = self.controller.pet.geometry()
        x = pet_geo.x() + (pet_geo.width() - self.reminder_bubble.width()) // 2
        y = pet_geo.y() - self.reminder_bubble.height() - 16
        y = max(0, y)
        self.reminder_bubble.move(x, y)

        self.reminder_bubble.show()
        self.reminder_bubble.raise_()
        self.bubble_timer.start(20000)

    def _play_sound(self):
        self._player.setPosition(0)
        self._player.play()

    # ===== 核心检查逻辑 =====
    def _check_class(self):
        now = datetime.now()
        weekday = now.isoweekday()
        now_time = now.strftime("%H:%M")

        if now_time == "00:00":
            self._reminded_today.clear()

        for course in self.schedule_list:
            if course["weekday"] != weekday:
                continue

            course_key = f"{course['name']}_{course['start']}"
            if course_key in self._reminded_today:
                continue

            now_q = QTime.fromString(now_time, "HH:mm")
            start_q = QTime.fromString(course["start"], "HH:mm")
            minutes_left = now_q.secsTo(start_q) // 60

            if 0 < minutes_left <= 15:
                self._trigger_reminder(course)
                self._reminded_today.add(course_key)

    def _trigger_reminder(self, course):
        text = f"📚 即将上课：{course['name']}\n📍 教室：{course['room']}\n⏰ {course['start']} 开始"
        self._show_bubble(text)
        self._play_sound()
        self.controller.chat.append("课程表", text)

    # ===== 调用入口 =====
    def open_settings(self):
        """外部调用入口：打开课程表设置"""
        dialog = ScheduleDialog(self.schedule_list, self.controller.pet)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.schedule_list = dialog.get_result()
            self._save_schedule()
            self._reminded_today.clear()
            self.controller.chat.append("课程表", "✅ 课程表已更新")

    def _bind_entry(self):
        """绑定调用入口：托盘菜单 + 聊天命令"""
        # 入口1：将课程表选项插入到「退出」上方
        tray_menu = self.controller.tray.menu
        
        # 找到菜单里的「退出」动作
        quit_action = None
        for action in tray_menu.actions():
            if action.text() == "退出":
                quit_action = action
                break
        
        if quit_action:
            # 先创建完整的 QAction 对象
            schedule_action = QAction("📚 课程表设置", tray_menu)
            schedule_action.triggered.connect(self.open_settings)
            # 插入到退出动作的前面
            tray_menu.insertAction(quit_action, schedule_action)
        else:
            # 找不到退出就追加到末尾（兜底）
            schedule_action = tray_menu.addAction("📚 课程表设置")
            schedule_action.triggered.connect(self.open_settings)

        # 入口2：聊天框输入「课程表」打开设置
        if hasattr(self.controller.chat, 'message_sent'):
            self.controller.chat.message_sent.connect(self._on_chat_command)


    def _on_chat_command(self, text: str):
        if text.strip() in ["课程表", "打开课程表", "课表设置"]:
            self.open_settings()

    # ===== 卸载清理 =====
    def on_unload(self):
        self.check_timer.stop()
        self.reminder_bubble.hide()
        self._player.stop()


# ===== 课程表设置窗口 =====
class ScheduleDialog(QDialog):
    def __init__(self, schedule_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("课程表设置")
        self.resize(420, 520)
        self.schedule_list = [item.copy() for item in schedule_list]
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(QLabel("已添加课程："))
        layout.addWidget(self.list_widget)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.room_edit = QLineEdit()
        self.weekday_spin = QSpinBox()
        self.weekday_spin.setRange(1, 7)
        self.weekday_spin.setSuffix("  (1=周一,7=周日)")
        self.start_edit = QLineEdit()
        self.start_edit.setPlaceholderText("格式：08:00")
        self.end_edit = QLineEdit()
        self.end_edit.setPlaceholderText("格式：09:40")

        form.addRow("课程名称：", self.name_edit)
        form.addRow("上课教室：", self.room_edit)
        form.addRow("星期：", self.weekday_spin)
        form.addRow("开始时间：", self.start_edit)
        form.addRow("结束时间：", self.end_edit)
        layout.addLayout(form)

        btn_row1 = QHBoxLayout()
        add_btn = QPushButton("添加课程")
        add_btn.clicked.connect(self._add_course)
        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._delete_course)
        btn_row1.addWidget(add_btn)
        btn_row1.addWidget(del_btn)
        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        btn_row2.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        btn_row2.addWidget(cancel_btn)
        btn_row2.addWidget(save_btn)
        layout.addLayout(btn_row2)

    def _refresh_list(self):
        self.list_widget.clear()
        week_map = ["一", "二", "三", "四", "五", "六", "日"]
        for c in self.schedule_list:
            text = f"周{week_map[c['weekday']-1]} {c['start']}-{c['end']} | {c['name']} ({c['room']})"
            QListWidgetItem(text, self.list_widget)

    def _add_course(self):
        name = self.name_edit.text().strip()
        start = self.start_edit.text().strip()
        if not name or not start:
            QMessageBox.warning(self, "提示", "课程名和开始时间不能为空")
            return

        self.schedule_list.append({
            "name": name,
            "room": self.room_edit.text().strip(),
            "weekday": self.weekday_spin.value(),
            "start": start,
            "end": self.end_edit.text().strip()
        })
        self.schedule_list.sort(key=lambda x: (x["weekday"], x["start"]))
        self._refresh_list()
        self.name_edit.clear()
        self.room_edit.clear()
        self.start_edit.clear()
        self.end_edit.clear()

    def _delete_course(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.schedule_list.pop(row)
            self._refresh_list()

    def get_result(self):
        return self.schedule_list
