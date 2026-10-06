from copy import deepcopy
import json

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from smart_desktop_pet.characters.catalog import Character, CharacterCatalog
from smart_desktop_pet.controller import PetController
from smart_desktop_pet.domain.emotion import Emotion
from smart_desktop_pet.memory.store import MemoryStore
from smart_desktop_pet.rendering.pet_window import PetWindow
from smart_desktop_pet.ui.chat_dialog import ChatDialog


def test_builtins_have_distinct_animated_transparent_states(app, tmp_path):
    catalog = CharacterCatalog(tmp_path)
    characters = catalog.list()
    assert len(characters) == 2
    for character in characters:
        pack = catalog.load(character)
        assert set(pack.frames) == set(Emotion)
        assert all(len(frames) == 12 for frames in pack.frames.values())
        idle = pack.frames[Emotion.IDLE]
        assert idle[0] != idle[3]
        assert idle[0] != pack.frames[Emotion.ANGRY][0]
        assert idle[0].pixelColor(0, 0).alpha() == 0


def test_image_import_produces_reloadable_pack(app, tmp_path):
    source = QImage(150, 200, QImage.Format.Format_ARGB32)
    source.fill(QColor("#12a185"))
    path = tmp_path / "example.png"
    assert source.save(str(path))
    catalog = CharacterCatalog(tmp_path)
    character = catalog.import_image(path, "测试角色")
    assert len(catalog.list()) == 3
    assert len(list(character.directory.rglob("*.png"))) == 32
    assert not list(catalog.directory.glob(".import-*"))
    pack = catalog.load(character)
    assert len(pack.frames[Emotion.HAPPY]) == 8
    assert pack.frames[Emotion.HAPPY][0] != pack.frames[Emotion.HAPPY][2]


def test_manifest_cannot_read_outside_pack(app, tmp_path):
    catalog = CharacterCatalog(tmp_path)
    folder = catalog.directory / "malicious"
    folder.mkdir()
    (folder / "character.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "Bad pack",
                "animations": {"idle": {"frames": ["../../outside.png"]}},
            }
        )
    )
    with pytest.raises(ValueError, match="角色包之外"):
        catalog.load(Character("malicious", "Bad pack", directory=folder))


def test_click_and_drag_are_separate_events(app):
    pet = PetWindow()
    clicks, moves = [], []
    pet.clicked.connect(lambda: clicks.append(True))
    pet.moved.connect(lambda: moves.append(True))
    pet.move(50, 50)
    pet.show()
    QTest.qWait(30)
    QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(140, 140))
    assert len(clicks) == 1
    start = pet.pos()
    QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(140, 140))
    QTest.mouseMove(pet, QPoint(200, 180), delay=30)
    QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(200, 180))
    assert len(clicks) == 1
    assert len(moves) == 1
    assert pet.pos() != start
    assert pet.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pet.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    pet.hide()
    pet.deleteLater()


def test_chat_renders_untrusted_output_as_plain_text(app):
    chat = ChatDialog()
    chat.append("模型", "<img src='file:///secret'> & <b>文本</b>")
    assert "<img src='file:///secret'>" in chat.history.toPlainText()
    assert "<b>文本</b>" in chat.history.toPlainText()
    chat.deleteLater()


def test_end_to_end_demo_memory_settings_switch_and_shutdown(app, wait_until, tmp_path):
    controller = PetController(app, tmp_path)
    try:
        controller.start(tray=False)
        controller.show_chat()
        controller.chat.input.setText("记住：我喜欢猫，谢谢你")
        controller.chat._send()
        wait_until(lambda: not controller.client.busy)
        profile = controller.memory.profile("builtin-cat")
        assert len(profile["turns"]) == 1
        assert profile["fragments"] == ["我喜欢猫，谢谢你"]
        assert controller.chat.input.text() == ""
        controller.show_settings()
        controller.settings.character.setCurrentIndex(1)
        controller.settings.persona.setPlainText("你是月光兔，说话很安静。")
        controller.settings.opacity.setValue(80)
        controller.settings.speed.setValue(1.5)
        controller.settings._apply()
        assert controller.character.id == "builtin-rabbit"
        assert controller.config.persona == "你是月光兔，说话很安静。"
        assert controller.config.opacity == 0.8
        assert controller.animator.speed == 1.5
        assert controller.memory.profile("builtin-rabbit")["turns"] == []
        assert not controller.settings.isVisible()
        controller.pet.hide()
        assert not controller.animator.timer.isActive()
        controller.pet.show()
        assert controller.animator.timer.isActive()
        persisted = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert "api_key" not in persisted
        assert persisted["character_id"] == "builtin-rabbit"
    finally:
        controller.shutdown()
    restored = MemoryStore(tmp_path)
    assert len(restored.profile("builtin-cat")["turns"]) == 1


def test_switching_character_cancels_inflight_chat(app, tmp_path):
    controller = PetController(app, tmp_path)
    try:
        controller.send("不能串入另一个角色")
        candidate = deepcopy(controller.config)
        candidate.character_id = "builtin-rabbit"
        controller.apply_settings(candidate, "")
        QTest.qWait(450)
        assert not controller.client.busy
        assert controller.memory.profile("builtin-cat")["turns"] == []
        assert controller.memory.profile("builtin-rabbit")["turns"] == []
    finally:
        controller.shutdown()
