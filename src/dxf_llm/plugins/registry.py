"""プラグインレジストリ

- 手動登録: registry.register(MyPlugin)
- 自動発見: entry points (pyproject.toml [project.entry-points."dxf_llm.plugins"])
- YAML 設定: recipes/plugins.yaml からインスタンス化

また、プラグインインスタンスを「名前 → インスタンス」で管理し、
ワークフロー実行時に再利用可能にする。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import Any, Dict, List, Optional, Type

from .base import PluginBase, HookManager

logger = logging.getLogger(__name__)


class PluginRegistry:
    """プラグインクラス・インスタンスの一元管理。"""

    def __init__(self, hook_manager: Optional[HookManager] = None) -> None:
        self._plugin_classes: Dict[str, Type[PluginBase]] = {}
        self._instances: Dict[str, PluginBase] = {}
        self._hook_manager = hook_manager or HookManager()

    # --- クラス登録 ---------------------------------------------------------

    def register_class(self, plugin_cls: Type[PluginBase]) -> None:
        """プラグインクラスを登録（name 属性をキー）。"""
        if not hasattr(plugin_cls, "name"):
            raise ValueError(f"Plugin class {plugin_cls} has no 'name' attribute")
        if plugin_cls.name in self._plugin_classes:
            logger.warning("Plugin %s already registered, overwriting", plugin_cls.name)
        self._plugin_classes[plugin_cls.name] = plugin_cls
        logger.debug("Registered plugin class: %s", plugin_cls.name)

    def register_from_entry_points(self, group: str = "dxf_llm.plugins") -> int:
        """setuptools entry points から自動発見・登録。"""
        count = 0
        try:
            for ep in importlib.metadata.entry_points(group=group):
                try:
                    plugin_cls = ep.load()
                    self.register_class(plugin_cls)
                    count += 1
                    logger.info("Discovered plugin via entry point: %s (%s)", ep.name, group)
                except Exception as exc:
                    logger.warning("Failed to load entry point %s: %s", ep.name, exc)
        except Exception as exc:
            logger.debug("Entry point discovery skipped: %s", exc)
        return count

    # --- インスタンス管理 ----------------------------------------------------

    def get_instance(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> PluginBase:
        """プラグインインスタンスを取得（なければ生成・setup）。"""
        if name not in self._instances:
            plugin_cls = self._plugin_classes.get(name)
            if not plugin_cls:
                raise KeyError(f"Plugin class not registered: {name}")
            instance = plugin_cls(config=config)
            if self._hook_manager:
                pass  # 共通フックを渡す（プラグイン側で self.hooks として利用可能にするなら別途設定）
            instance.setup()
            self._instances[name] = instance
        return self._instances[name]

    def get_or_create(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> PluginBase:
        """get_instance のエイリアス（より明示的）。"""
        return self.get_instance(name, config)

    def list_plugins(self) -> List[str]:
        """登録済みプラグイン名一覧。"""
        return list(self._plugin_classes.keys())

    def list_instances(self) -> List[str]:
        """初期化済みインスタンス名一覧。"""
        return list(self._instances.keys())

    # --- ライフサイクル ------------------------------------------------------

    def teardown_all(self) -> None:
        """全インスタンスの teardown を呼ぶ。"""
        for inst in self._instances.values():
            try:
                inst.teardown()
            except Exception as exc:
                logger.exception("Teardown failed for %s: %s", inst.name, exc)
        self._instances.clear()

    # --- フックアクセス -------------------------------------------------------

    @property
    def hooks(self) -> HookManager:
        return self._hook_manager


# グローバルレジストリ（シンプルな利用用）
_global_registry: Optional[PluginRegistry] = None


def get_global_registry() -> PluginRegistry:
    """グローバルレジストリを取得（なければ作成）。"""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
        _global_registry.register_from_entry_points()
    return _global_registry


def register_plugin(plugin_cls: Type[PluginBase]) -> None:
    """グローバルレジストリへクラス登録（import 時に呼ばれる想定）。"""
    get_global_registry().register_class(plugin_cls)