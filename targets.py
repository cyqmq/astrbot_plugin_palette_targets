"""AstrBot Dashboard 入口目标发现。

集中实现 AstrBot Dashboard 目标（data/dist、内置、自定义 --webui-dir）的
解析逻辑，供 astrbot_plugin_palette 等插件通过 Python API 或 HTTP API 调用，
避免各插件重复硬编码 data/dist/index.html。

暴露：
- Python API：get_dashboard_targets(custom_dist=None) -> list[dict]
              get_recommended_target(custom_dist=None) -> dict | None
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
except Exception:  # pragma: no cover
    get_astrbot_data_path = None

try:
    from astrbot.core.config.default import VERSION as ASTRBOT_VERSION
except Exception:  # pragma: no cover - 缺少 AstrBot 的环境
    ASTRBOT_VERSION = ""

try:
    # AstrBot 4.27.x 起的公开 Dashboard 目录解析器
    from astrbot.core.dashboard_assets import resolve_dashboard_dist
except Exception:  # pragma: no cover - 兼容 4.26.x 及更早
    resolve_dashboard_dist = None

try:
    # AstrBot 4.26.x 的旧版 Dashboard 辅助函数
    from astrbot.core.utils.io import (
        get_bundled_dashboard_dist_path,
        is_dashboard_dist_compatible,
        should_use_bundled_dashboard_dist,
    )
except Exception:  # pragma: no cover - 兼容 4.27.x 及更早
    get_bundled_dashboard_dist_path = None
    is_dashboard_dist_compatible = None
    should_use_bundled_dashboard_dist = None


@dataclass
class DashboardTarget:
    """描述一个可注入的 Dashboard 入口。"""

    dist: str
    index: str
    source: str
    compatible: bool | None
    restart_required: bool = False
    fallback_target: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # 兼容 palette 内部 DashboardTarget 的 Path 字段
        return d


def _same_dist(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _compatibility(dist: Path) -> bool | None:
    if is_dashboard_dist_compatible is None or not ASTRBOT_VERSION:
        return None
    try:
        return bool(is_dashboard_dist_compatible(dist, ASTRBOT_VERSION))
    except Exception:
        return False


def _is_compatible(dist: Path) -> bool:
    return _compatibility(dist) is True


def _from_dist(
    dist: Path,
    source: str,
    *,
    compatible: bool | None = None,
    restart_required: bool = False,
    fallback_target: str = "",
) -> DashboardTarget:
    return DashboardTarget(
        dist=str(dist),
        index=str(dist / "index.html"),
        source=source,
        compatible=compatible,
        restart_required=restart_required,
        fallback_target=fallback_target,
    )


def _custom_dashboard_dist() -> Path | None:
    """从 AstrBot 启动参数解析自定义 --webui-dir。"""
    argv = sys.argv[1:]
    for idx, arg in enumerate(argv):
        if arg.startswith("--webui-dir="):
            value = arg.split("=", 1)[1].strip()
            if value:
                dist = Path(value).expanduser()
                if dist.exists():
                    return dist.resolve()
            return None
        if arg != "--webui-dir":
            continue
        if idx + 1 >= len(argv):
            return None
        value_parts: list[str] = []
        for value_arg in argv[idx + 1 :]:
            if value_arg.startswith("-"):
                break
            if value_arg:
                value_parts.append(value_arg)
        value = " ".join(value_parts).strip()
        if value:
            dist = Path(value).expanduser()
            if dist.exists():
                return dist.resolve()
        return None
    return None


def _bundled_target() -> DashboardTarget | None:
    if get_bundled_dashboard_dist_path is None:
        return None
    try:
        dist = Path(get_bundled_dashboard_dist_path())
    except Exception:
        return None
    return _from_dist(dist, "bundled", compatible=_compatibility(dist))


def _should_use_bundled(user_dist: Path) -> bool:
    if should_use_bundled_dashboard_dist is None or not ASTRBOT_VERSION:
        return False
    try:
        return bool(should_use_bundled_dashboard_dist(user_dist, ASTRBOT_VERSION))
    except Exception:
        return False


def _resolve_with_public_resolver(custom_dist: Path | None) -> Path | None:
    """通过 AstrBot 公开解析器获取实际服务的 Dashboard 目录。"""
    if resolve_dashboard_dist is None:
        return None
    try:
        dist = (
            resolve_dashboard_dist(custom_dist)
            if custom_dist is not None
            else resolve_dashboard_dist()
        )
    except Exception:
        return None
    if dist is None:
        return None
    return Path(dist)


def get_dashboard_targets(custom_dist: Path | None = None) -> list[dict]:
    """返回全部候选 Dashboard 目标（dict 列表，可 JSON 序列化）。

    依次包含：
    - public resolver 选中的目录（data/dist 或 bundled 或 custom）
    - data/dist（用户目录）
    - bundled（AstrBot 内置）
    - custom（--webui-dir）
    """
    targets: list[dict] = []

    resolved = _resolve_with_public_resolver(custom_dist)
    if resolved is not None:
        targets.append(
            _from_dist(resolved, "resolved").to_dict()
        )

    if get_astrbot_data_path is not None:
        user_dist = Path(get_astrbot_data_path()) / "dist"
        if user_dist.exists():
            targets.append(
                _from_dist(
                    user_dist,
                    "data/dist",
                    compatible=_compatibility(user_dist),
                ).to_dict()
            )

    bundled = _bundled_target()
    if bundled is not None:
        targets.append(bundled.to_dict())

    custom = custom_dist or _custom_dashboard_dist()
    if custom is not None:
        targets.append(
            _from_dist(
                custom,
                "custom",
                compatible=_compatibility(custom),
            ).to_dict()
        )

    # 去重（按 dist 路径）
    seen: set[str] = set()
    deduped: list[dict] = []
    for t in targets:
        key = t["dist"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)
    return deduped


def get_recommended_target(custom_dist: Path | None = None) -> dict | None:
    """返回推荐使用的 Dashboard 目标（优先兼容的 data/dist，其次 bundled）。

    与 palette 原 _resolve_dashboard_target 的选择策略对齐。
    """
    targets = get_dashboard_targets(custom_dist)
    if not targets:
        return None

    # 1. 优先 compatible=True 的 data/dist
    for t in targets:
        if t["source"] == "data/dist" and t["compatible"] is True:
            return t
    # 2. 其次 compatible=True 的 resolved/bundled
    for t in targets:
        if t["compatible"] is True:
            return t
    # 3. 最后第一个可用目标
    return targets[0]