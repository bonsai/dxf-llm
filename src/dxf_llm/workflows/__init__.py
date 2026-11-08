"""ワークフローエンジン (DAG ベース)

pyper 風の DAG 実行エンジン。
Step 定義 → 依存グラフ構築 → トポロジカルソート → 順次/並列実行。

Bonsai の Operator/ExecutionContext の概念も取り入れ、
- context: 共有データストア（ステップ間データ受け渡し）
- hooks: before_<step>/after_<step>/on_error
- retry/timeout/retry_policy
をサポート。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING

from ..plugins.base import HookManager
from ..plugins.registry import PluginRegistry

if TYPE_CHECKING:
    from ..plugins.base import PluginBase

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """ステップ実行結果。"""
    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepConfig:
    """ワークフロー定義上の 1 ステップ設定。"""
    id: str                                    # 一意 ID
    plugin: str                                # 実行するプラグイン名（registry で解決）
    params: Dict[str, Any] = field(default_factory=dict)  # プラグイン固有パラメータ
    depends_on: List[str] = field(default_factory=list)   # 依存ステップ ID 列
    condition: Optional[str] = None            # Python 式（context 変数で評価）
    retry: int = 0                             # リトライ回数
    timeout: float = 300.0                     # タイムアウト秒
    skip_on_failure: bool = False              # 依存失敗時にスキップ


class Step:
    """実行時ステップオブジェクト。"""

    def __init__(
        self,
        config: StepConfig,
        plugin_instance: "PluginBase",
        hooks: HookManager,
    ) -> None:
        self.config = config
        self.plugin = plugin_instance
        self.hooks = hooks
        self.status = StepStatus.PENDING
        self.result: Optional[StepResult] = None

    def _eval_condition(self, context: Dict[str, Any]) -> bool:
        """condition 式を評価。context 変数をローカルスコープに展開して eval。"""
        if not self.config.condition:
            return True
        try:
            # 安全のため組み込み関数のみ許可（必要なら拡張）
            safe_globals = {"__builtins__": {}}
            return bool(eval(self.config.condition, safe_globals, context))
        except Exception as exc:
            logger.warning("Condition eval failed for %s: %s", self.config.id, exc)
            return False

    def _prepare_input(self, context: Dict[str, Any]) -> Any:
        """依存ステップの出力を収集してプラグイン入力 data とする。
        単一依存ならその output、複数なら dict で渡す。"""
        dep_outputs = {}
        for dep_id in self.config.depends_on:
            if dep_id in context:
                dep_outputs[dep_id] = context[dep_id]
        if len(dep_outputs) == 1:
            return next(iter(dep_outputs.values()))
        return dep_outputs if dep_outputs else None

    def execute(self, context: Dict[str, Any]) -> StepResult:
        """ステップ実行。リトライ・タイムアウト・フック込み。"""
        if not self._eval_condition(context):
            self.status = StepStatus.SKIPPED
            return StepResult(
                step_id=self.config.id,
                status=StepStatus.SKIPPED,
                output=None,
                error="Condition not met",
            )

        self.status = StepStatus.RUNNING
        self.hooks.run(f"before_{self.config.id}", context)

        last_error = None
        for attempt in range(self.config.retry + 1):
            start = time.time()
            try:
                input_data = self._prepare_input(context)
                output = self.plugin.execute(input_data, context)
                duration = time.time() - start

                self.status = StepStatus.SUCCESS
                self.result = StepResult(
                    step_id=self.config.id,
                    status=StepStatus.SUCCESS,
                    output=output,
                    duration=duration,
                )
                context[self.config.id] = output  # 次ステップ用に保存
                self.hooks.run(f"after_{self.config.id}", context, output)
                return self.result

            except Exception as exc:
                last_error = exc
                duration = time.time() - start
                logger.warning(
                    "Step %s attempt %d/%d failed: %s",
                    self.config.id,
                    attempt + 1,
                    self.config.retry + 1,
                    exc,
                )
                if attempt < self.config.retry:
                    time.sleep(0.5 * (attempt + 1))  # 指数バックオフ簡易
                    continue

        # 全リトライ失敗
        self.status = StepStatus.FAILED
        self.result = StepResult(
            step_id=self.config.id,
            status=StepStatus.FAILED,
            error=str(last_error),
            duration=0.0,
        )
        self.hooks.run("on_error", context, self.config.id, last_error)
        return self.result


class Workflow:
    """DAG ワークフロー定義と実行エンジン。"""

    def __init__(
        self,
        steps: List[StepConfig],
        registry: PluginRegistry,
        name: str = "workflow",
    ) -> None:
        self.name = name
        self.steps_config = {s.id: s for s in steps}
        self.registry = registry
        self.hooks = HookManager()
        self._validate_dag()
        self._build_execution_plan()

    def _validate_dag(self) -> None:
        """依存グラフの妥当性チェック（サイクル検出・未定義参照）。"""
        # 未定義依存チェック
        all_ids = set(self.steps_config.keys())
        for step in self.steps_config.values():
            for dep in step.depends_on:
                if dep not in all_ids:
                    raise ValueError(f"Step {step.id} depends on unknown step: {dep}")

        # サイクル検出（Kahn's algorithm）
        in_degree = {sid: 0 for sid in all_ids}
        graph = {sid: set() for sid in all_ids}
        for step in self.steps_config.values():
            for dep in step.depends_on:
                graph[dep].add(step.id)
                in_degree[step.id] += 1

        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for nxt in graph[node]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        if visited != len(all_ids):
            raise ValueError("Cycle detected in workflow DAG")

    def _build_execution_plan(self) -> None:
        """トポロジカルソートで実行順序を決定（レベルごとに並列可）。"""
        # Kahn's algorithm でレベル分け
        in_degree = {sid: 0 for sid in self.steps_config}
        graph = {sid: set() for sid in self.steps_config}
        for step in self.steps_config.values():
            for dep in step.depends_on:
                graph[dep].add(step.id)
                in_degree[step.id] += 1

        levels: List[List[str]] = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        while queue:
            level_size = len(queue)
            current_level = []
            for _ in range(level_size):
                node = queue.popleft()
                current_level.append(node)
                for nxt in graph[node]:
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        queue.append(nxt)
            levels.append(current_level)
        self.execution_levels = levels

    def _instantiate_step(self, step_id: str) -> Step:
        """StepConfig から Step 実行オブジェクトを生成。"""
        config = self.steps_config[step_id]
        plugin_instance = self.registry.get_instance(config.plugin)
        return Step(config, plugin_instance, self.hooks)

    def run(
        self,
        initial_context: Optional[Dict[str, Any]] = None,
        parallel: bool = False,
    ) -> Dict[str, StepResult]:
        """ワークフロー実行。

        Args:
            initial_context: 初期コンテキスト（入力ファイルパス等）
            parallel: True で同一レベル内を並列実行（threading）

        Returns:
            step_id -> StepResult の辞書
        """
        context = initial_context or {}
        context["_workflow_id"] = str(uuid.uuid4())[:8]
        context["_workflow_name"] = self.name

        logger.info("Starting workflow: %s (%s)", self.name, context["_workflow_id"])

        self.hooks.run("on_start", context)

        results: Dict[str, StepResult] = {}

        try:
            if parallel:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    for level in self.execution_levels:
                        # 依存失敗チェック
                        failed_deps = {
                            dep for dep, res in results.items()
                            if res.status == StepStatus.FAILED
                        }
                        ready = [sid for sid in level if sid not in failed_deps]
                        skipped = [sid for sid in level if sid in failed_deps]

                        for sid in skipped:
                            step = self._instantiate_step(sid)
                            step.status = StepStatus.SKIPPED
                            results[sid] = StepResult(
                                step_id=sid,
                                status=StepStatus.SKIPPED,
                                error="Dependency failed",
                            )

                        if ready:
                            future_to_sid = {
                                executor.submit(self._instantiate_step(sid).execute, context): sid
                                for sid in ready
                            }
                            for future in concurrent.futures.as_completed(future_to_sid):
                                sid = future_to_sid[future]
                                try:
                                    res = future.result()
                                except Exception as exc:
                                    res = StepResult(
                                        step_id=sid,
                                        status=StepStatus.FAILED,
                                        error=str(exc),
                                    )
                                results[sid] = res
            else:
                # 直列実行（レベル順）
                for level in self.execution_levels:
                    failed_deps = {
                        dep for dep, res in results.items()
                        if res.status == StepStatus.FAILED
                    }
                    for sid in level:
                        if sid in failed_deps and self.steps_config[sid].skip_on_failure:
                            step = self._instantiate_step(sid)
                            step.status = StepStatus.SKIPPED
                            results[sid] = StepResult(
                                step_id=sid,
                                status=StepStatus.SKIPPED,
                                error="Dependency failed",
                            )
                            continue

                        step = self._instantiate_step(sid)
                        res = step.execute(context)
                        results[sid] = res

            self.hooks.run("on_complete", context, results)
            logger.info("Workflow completed: %s", self.name)
            return results

        except Exception as exc:
            self.hooks.run("on_workflow_error", context, exc)
            logger.exception("Workflow failed: %s", exc)
            raise

    def get_step_result(self, results: Dict[str, StepResult], step_id: str) -> Any:
        """結果から特定ステップの output を安全に取得。"""
        res = results.get(step_id)
        if res and res.status == StepStatus.SUCCESS:
            return res.output
        return None


# --- YAML ローダー -----------------------------------------------------------

def load_workflow_from_yaml(
    yaml_path: str,
    registry: PluginRegistry,
) -> Workflow:
    """YAML ファイルから Workflow を構築。

    YAML 例:
    ```yaml
    name: dxf_to_bim
    steps:
      - id: parse
        plugin: dxf_parser
        params:
          encoding: cp932
      - id: enrich
        plugin: semantic_enricher
        depends_on: [parse]
      - id: export_ifc
        plugin: ifc_exporter
        depends_on: [enrich]
    ```
    """
    import yaml

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    steps = [StepConfig(**s) for s in data.get("steps", [])]
    return Workflow(steps, registry, name=data.get("name", "workflow"))