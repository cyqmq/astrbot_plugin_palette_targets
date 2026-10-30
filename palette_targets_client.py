"""其他插件接入 astrbot_plugin_palette_targets 的适配客户端。

把这个文件复制到你的插件目录（如 <你的插件>/palette_targets_client.py），
即可通过统一接口获取 AstrBot Dashboard 目标列表，无需关心附属插件是否安装。

用法：
    from palette_targets_client import (
        get_dashboard_targets,   # -> list[dict]
        get_recommended_target,  # -> dict | None
        get_dashboard_paths,     # -> list[TargetPaths]（Path 对象）
        get_recommended_paths,   # -> TargetPaths | None
    )

原理：
    1. 若已安装 astrbot_plugin_palette_targets，import 其 Python API；
    2. 否则回退到本文件的轻量解析（data/dist + bundled 兼容导入）；
    3. 统一返回 JSON 可序列化的 dict 或 Path 对象。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------- 首选：附属插件已安装 ----------

try:
    from astrbot_plugin_palette_targets.targets import (
        get_dashboard_targets as _companion_get_targets,
        get_recommended_target as _companion_get_recommended,
    )
except Exception:  # 附属插件未安装
    _companion_get_targets = None
    _companion_get_recommended = None


# ---------- 回退：本地轻量解析 ----------

def _local_data_dist() -> Path | None:
    """回退：定位 AstrBot data/dist。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        dist = Path(get_astrbot_data_path()) / "dist"
        return dist if dist.exists() else None
    except Exception:
        return None


def _local_bundled_dist() -> Path | None:
    """回退：定位 AstrBot 内置 dist（4.26+）。"""
    try:
        from astrbot.core.utils.io import get_bundled_dashboard_dist_path

        return Path(get_bundled_dashboard_dist_path())
    except Exception:
        return None


def _local_targets() -> list[dict]:
    """回退：返回本地可发现的目标列表。"""
    targets: list[dict] = []
    user_dist = _local_data_dist()
    if user_dist is not None:
        targets.append(
            {
                "dist": str(user_dist),
                "index": str(user_dist / "index.html"),
                "source": "data/dist",
                "compatible": None,
                "restart_required": False,
                "fallback_target": "",
            }
        )
    bundled = _local_bundled_dist()
    if bundled is not None and bundled.exists():
        targets.append(
            {
                "dist": str(bundled),
                "index": str(bundled / "index.html"),
                "source": "bundled",
                "compatible": None,
                "restart_required": False,
                "fallback_target": "",
            }
        )
    return targets


# ---------- 对外统一 API ----------

def get_dashboard_targets() -> list[dict]:
    """返回 AstrBot Dashboard 候选目标列表（dict，可 JSON 序列化）。"""
    if _companion_get_targets is not None:
        try:
            return _companion_get_targets()
        except Exception:
            pass
    return _local_targets()


def get_recommended_target() -> dict | None:
    """返回推荐使用的 Dashboard 目标。"""
    if _companion_get_recommended is not None:
        try:
            return _companion_get_recommended()
        except Exception:
            pass
    targets = _local_targets()
    return targets[0] if targets else None


@dataclass(frozen=True)
class TargetPaths:
    """用 Path 对象表达的目标，方便直接读写文件。"""

    dist: Path
    index: Path
    source: str
    compatible: bool | None = None
    restart_required: bool = False
    fallback_target: str = ""


def get_dashboard_paths() -> list[TargetPaths]:
    """返回目标列表（Path 对象）。"""
    return [TargetPaths(**{k: (Path(v) if k in ("dist", "index") else v) for k, v in t.items()}) for t in get_dashboard_targets()]


def get_recommended_paths() -> TargetPaths | None:
    """返回推荐目标（Path 对象）。"""
    t = get_recommended_target()
    if t is None:
        return None
    return TargetPaths(
        dist=Path(t["dist"]),
        index=Path(t["index"]),
        source=t["source"],
        compatible=t.get("compatible"),
        restart_required=bool(t.get("restart_required", False)),
        fallback_target=t.get("fallback_target", ""),
    )


# ---------- 示例：检查/注入 index.html ----------

def ensure_index_writable() -> bool:
    """示例：检查推荐目标 index.html 是否存在且可写。"""
    target = get_recommended_paths()
    if target is None:
        return False
    return target.index.is_file() and target.index.exists()