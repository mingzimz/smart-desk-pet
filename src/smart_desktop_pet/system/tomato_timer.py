from PySide6.QtCore import QTimer, Signal, QObject

class TomatoTimer(QObject):
    # 信号定义
    tick_signal = Signal(int)          # 每秒触发，传递剩余秒数
    finished_signal = Signal(str)      # 阶段完成，参数：work / rest
    state_changed_signal = Signal(str) # 状态切换：idle / work / rest

    def __init__(self):
        super().__init__()
        self._qt_timer = QTimer(self)
        self._qt_timer.timeout.connect(self._on_tick)
        self._qt_timer.setInterval(1000)

        # 状态变量
        self.state = "idle"
        self.remain_seconds = 0
        self.work_seconds = 25 * 60
        self.rest_seconds = 5 * 60
        self._paused = False  # 新增：标记是否处于暂停状态


    def set_work_minutes(self, minutes: int):
        """设置工作分钟数"""
        self.work_seconds = minutes * 60

    def set_rest_minutes(self, minutes: int):
        """设置休息分钟数"""
        self.rest_seconds = minutes * 60

    def start_work(self):
        self._paused = False
        self.state = "work"
        self.remain_seconds = self.work_seconds
        self.state_changed_signal.emit(self.state)
        self._qt_timer.start()

    def start_rest(self):
        self._paused = False
        self.state = "rest"
        self.remain_seconds = self.rest_seconds
        self.state_changed_signal.emit(self.state)
        self._qt_timer.start()

    def pause(self):
        # 只有计时器正在运行时才执行暂停
        if self._qt_timer.isActive():
            self._qt_timer.stop()
            self._paused = True

    def resume(self):
        self._qt_timer.start()

    def reset(self):
        self._paused = False
        self._qt_timer.stop()
        self.state = "idle"
        self.remain_seconds = 0
        self.state_changed_signal.emit(self.state)

    def _on_tick(self):
        self.remain_seconds -= 1
        self.tick_signal.emit(self.remain_seconds)
        if self.remain_seconds <= 0:
            self._qt_timer.stop()
            self.finished_signal.emit(self.state)
            self.state = "idle"
            self.state_changed_signal.emit(self.state)
