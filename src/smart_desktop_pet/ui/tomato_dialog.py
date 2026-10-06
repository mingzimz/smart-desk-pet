from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QSpinBox, QHBoxLayout
)
from PySide6.QtCore import Qt

class TomatoDialog(QWidget):
    def __init__(self, tomato_timer, parent=None):
        super().__init__(parent)
        self.tomato_timer = tomato_timer
        self.setWindowTitle("🍅 番茄钟")
        self.setFixedSize(320, 300)
        # 置顶，和项目其他对话框保持一致
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout()

        # 工作时长
        h_work = QHBoxLayout()
        h_work.addWidget(QLabel("工作时长(分钟)"))
        self.spin_work = QSpinBox()
        self.spin_work.setRange(1, 120)
        self.spin_work.setValue(25)
        h_work.addWidget(self.spin_work)
        layout.addLayout(h_work)

        # 休息时长
        h_rest = QHBoxLayout()
        h_rest.addWidget(QLabel("休息时长(分钟)"))
        self.spin_rest = QSpinBox()
        self.spin_rest.setRange(1, 60)
        self.spin_rest.setValue(5)
        h_rest.addWidget(self.spin_rest)
        layout.addLayout(h_rest)

        # 倒计时文本
        self.label_time = QLabel("待机")
        self.label_time.setAlignment(Qt.AlignCenter)
        self.label_time.setStyleSheet("font-size:18px; padding:10px;")
        layout.addWidget(self.label_time)
        self.label_time.setMinimumHeight(70)  # 强制标签至少70像素高
        self.label_time.setAlignment(Qt.AlignCenter)  # 文字垂直+水平居中

        # 按钮
        btn_start_work = QPushButton("开始工作")
        btn_start_work.clicked.connect(self.on_start_work)
        btn_start_rest = QPushButton("开始休息")
        btn_start_rest.clicked.connect(self.on_start_rest)
        self.btn_pause = QPushButton("暂停")
        self.btn_pause.clicked.connect(self._toggle_pause)
        btn_reset = QPushButton("重置")
        btn_reset.clicked.connect(self.on_reset)

        layout.addWidget(btn_start_work)
        layout.addWidget(btn_start_rest)
        layout.addWidget(self.btn_pause)
        layout.addWidget(btn_reset)
        layout.addWidget(self.label_time, stretch=1)  # stretch=1 让标签占据多余空间，不会被压缩

        self.setLayout(layout)

        # 绑定定时器信号
        self.tomato_timer.tick_signal.connect(self.update_time_text)
        self.tomato_timer.state_changed_signal.connect(self.on_state_change)

    def on_start_work(self):
        self.btn_pause.setText("暂停")  # 新增这行
        self.tomato_timer.set_work_minutes(self.spin_work.value())
        self.tomato_timer.start_work()

    def on_start_rest(self):
        self.btn_pause.setText("暂停")  # 新增这行
        self.tomato_timer.set_rest_minutes(self.spin_rest.value())
        self.tomato_timer.start_rest()

    def update_time_text(self, remain_sec):
        m = remain_sec // 60
        s = remain_sec % 60
        self.label_time.setText(f"剩余 {m:02d}:{s:02d}")

    def on_state_change(self, state):
        if state == "idle":
            self.label_time.setText("待机")
        elif state == "work":
            self.label_time.setText("🍅 工作中")
        elif state == "rest":
            self.label_time.setText("☕ 休息中")
    def _toggle_pause(self):
        if self.tomato_timer._paused:
            # 当前是暂停状态 → 继续
            self.tomato_timer.resume()
            self.btn_pause.setText("暂停")
        else:
            # 当前是运行状态 → 暂停
            self.tomato_timer.pause()
            self.btn_pause.setText("继续")
    def on_reset(self):
        self.btn_pause.setText("暂停")
        self.tomato_timer.reset()



