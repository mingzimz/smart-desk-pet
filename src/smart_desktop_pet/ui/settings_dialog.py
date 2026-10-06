from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from ..config.models import AppConfig, DEFAULT_PERSONA
from ..characters.catalog import Character
from .theme import STYLE


class SettingsDialog(QDialog):
    apply_requested = Signal(object, str)
    import_requested = Signal()

    def __init__(
        self, config: AppConfig, characters: list[Character], data_path: str, session_key: str
    ):
        super().__init__()
        self.setWindowTitle("设置 · SmartDesktopPet")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.resize(550, 580)
        self.config = deepcopy(config)
        self.active_id = config.character_id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        title = QLabel("让桌宠更懂你")
        title.setObjectName("title")
        layout.addWidget(title)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        model_tab = QWidget()
        model_form = QFormLayout(model_tab)
        model_form.setSpacing(12)
        self.provider = QComboBox()
        for label, value in (
            ("离线演示（无需模型）", "demo"),
            ("本地 Ollama", "ollama"),
            ("OpenAI 兼容 API", "openai"),
        ):
            self.provider.addItem(label, value)
        self.provider.setCurrentIndex(self.provider.findData(config.provider))
        self.url = QLineEdit(config.base_url)
        self.url.setPlaceholderText("http://localhost:11434 或 https://服务地址/v1")
        self.model = QLineEdit(config.model)
        self.key = QLineEdit(session_key)
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("仅本次运行；持久使用请设置下方环境变量")
        self.key_env = QLineEdit(config.api_key_env)
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 300)
        self.timeout.setSuffix(" 秒")
        self.timeout.setValue(config.timeout_seconds)
        for label, field in (
            ("对话方式", self.provider),
            ("服务地址", self.url),
            ("模型名称", self.model),
            ("API Key", self.key),
            ("Key 环境变量", self.key_env),
            ("请求超时", self.timeout),
        ):
            model_form.addRow(label, field)
        note = QLabel(
            "Ollama 地址填服务根路径；兼容 API 填含 /v1 的基础地址或完整 /chat/completions 地址。API Key 不写入 JSON。切换服务后请核对地址和模型名。"
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        model_form.addRow(note)
        tabs.addTab(model_tab, "模型连接")
        pet_tab = QWidget()
        pet_form = QFormLayout(pet_tab)
        pet_form.setSpacing(12)
        self.character = QComboBox()
        for character in characters:
            self.character.addItem(character.name, character.id)
        self.character.setCurrentIndex(self.character.findData(config.character_id))
        row = QHBoxLayout()
        row.addWidget(self.character, 1)
        add = QPushButton("导入图片")
        add.clicked.connect(self.import_requested.emit)
        row.addWidget(add)
        pet_form.addRow("角色", row)
        self.persona = QTextEdit()
        self.persona.setAcceptRichText(False)
        self.persona.setPlainText(config.persona)
        self.persona.setMinimumHeight(150)
        pet_form.addRow("独立人设", self.persona)
        self.character.currentIndexChanged.connect(self._change_character)
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.25, 3)
        self.speed.setSingleStep(0.25)
        self.speed.setSuffix(" 倍")
        self.speed.setValue(config.animation_speed)
        self.opacity = QSpinBox()
        self.opacity.setRange(20, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setValue(round(config.opacity * 100))
        pet_form.addRow("动画速度", self.speed)
        pet_form.addRow("不透明度", self.opacity)
        hint = QLabel(
            "单张图片可生成四种状态的位移动画，保留原背景。推荐透明 PNG；不会自动补画新姿态或抠图。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        pet_form.addRow(hint)
        tabs.addTab(pet_tab, "角色与外观")
        path_label = QLabel("数据目录：" + data_path)
        path_label.setTextFormat(Qt.TextFormat.PlainText)
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setObjectName("muted")
        layout.addWidget(path_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存并应用")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_character(self, character: Character):
        self.character.addItem(character.name, character.id)
        self.character.setCurrentIndex(self.character.count() - 1)

    def _change_character(self):
        self.config.personas[self.active_id] = self.persona.toPlainText().strip()
        self.active_id = self.character.currentData()
        self.persona.setPlainText(self.config.personas.get(self.active_id, DEFAULT_PERSONA))

    def _apply(self):
        candidate = deepcopy(self.config)
        candidate.provider = self.provider.currentData()
        candidate.base_url = self.url.text().strip()
        candidate.model = self.model.text().strip()
        candidate.api_key_env = self.key_env.text().strip()
        candidate.timeout_seconds = self.timeout.value()
        candidate.animation_speed = self.speed.value()
        candidate.opacity = self.opacity.value() / 100
        candidate.character_id = self.character.currentData()
        candidate.personas[candidate.character_id] = self.persona.toPlainText().strip()
        try:
            candidate.validate()
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, "请检查设置", str(exc))
            return
        self.apply_requested.emit(candidate, self.key.text().strip())
