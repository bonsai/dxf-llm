"""プラグイン基底クラスとフックマネージャ

Bonsai（BlenderBIM）を参考にしたプラグインアーキテクチャ。
外部からプラグインを登録・発見・実行可能にする。

 lifecycle:
  setup()   → 初期化（設定読込、リソース確保）
  execute() → 本処理（データ変換・計算・検索など）
  teardown()→ 後始末（リソース解放）

HookManager は「before_<step_id> / after_<step_id> / on_error」形式の
フックを登録・実行し、プラグイン間の疎結合な連携を可能にする。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PluginBase(ABC):
    """すべてのプラグインの基底クラス。

    Attributes:
        name: プラグイン固有名（一意。例: "dxf_parser"）
        version: バージョン文字列
        description: 簡易説明
        config: プラグイン固有設定（dict）
    """

    name: str = "base_plugin"
    version: str = "0.1.0"
    description: str = ""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._initialized = False

    def setup(self) -> None:
        """初期化。サブクラスでオーバーライド可能。"""
        self._initialized = True
        logger.debug("[%s] plugin setup done", self.name)

    @abstractmethod
    def execute(
        self, data: Any, context: Dict[str, Any]
    ) -> Any:
        """メイン処理。

        Args:
            data: 前ステップまたは外部から渡される入力データ
            context: ワークフロー全体の共有コンテキスト

        Returns:
            処理結果。次のステップやワークフロー出力として利用される。
        """
        raise NotImplementedError

    def teardown(self) -> None:
        """後始末。サブクラスでオーバーライド可能。"""
        self._initialized = False
        logger.debug("[%s] plugin teardown done", self.name)

    def is_initialized(self) -> bool:
        return self._initialized


class HookManager:
    """イベントフック管理。

    登録形式: "before_<step_id>" / "after_<step_id>" / "on_error" など
    複数コールバックを登録でき、順次実行される。
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, List[Callable[..., None]]] = {}

    def register(self, hook_name: str, callback: Callable[..., None]) -> None:
        """指定フック名にコールバックを登録。"""
        self._hooks.setdefault(hook_name, []).append(callback)
        logger.debug("Hook registered: %s -> %s", hook_name, getattr(callback, "__name__", callback))

    def unregister(self, hook_name: str, callback: Callable[..., None]) -> None:
        """指定フック名からコールバックを削除。"""
        callbacks = self._hooks.get(hook_name, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def run(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """指定フック名の全コールバックを順次実行。"""
        for cb in self._hooks.get(hook_name, []):
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                logger.exception("Hook %s callback failed: %s", hook_name, exc)