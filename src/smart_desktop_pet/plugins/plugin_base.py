from PySide6.QtCore import QObject

class PluginBase(QObject):
    """所有桌宠插件的基类，约定统一接口"""
    # 插件元信息（每个插件自己填）
    plugin_id = ""       # 插件唯一ID，不能重复
    plugin_name = ""     # 插件显示名称
    plugin_desc = ""     # 插件功能描述

    def __init__(self, controller):
        super().__init__(controller)
        # 保存核心控制器引用，插件通过它访问桌宠的所有能力
        # 比如 self.controller.chat 是聊天窗口，self.controller.pet 是桌宠窗口
        self.controller = controller

    def on_load(self):
        """插件加载完成时自动调用：初始化资源、绑定事件"""
        pass

    def on_unload(self):
        """插件卸载时自动调用：释放资源、保存数据"""
        pass
