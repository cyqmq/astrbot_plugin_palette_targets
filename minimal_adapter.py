"""最小接入器模板（其他插件复制本文件即可，约 25 行）。

设计原则：
- 附属插件 astrbot_plugin_palette_targets 持有完整的目标解析逻辑；
- 其他插件只内嵌这个「最小接入器」，不复制完整客户端；
- 接入器首选 import 附属插件 API，失败时仅回退到 data/dist 一次，
  避免每个插件都维护一大段解析代码。

用法：
    from minimal_adapter import get_dashboard_index

    index_path = get_dashboard_index()
    if index_path:
        content = index_path.read_text(encoding="utf-8")
        # ... 你的注入逻辑
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# 首选：附属插件已安装（完整解析：data/dist / bundled / --webui-dir）
try:
    from astrbot_plugin_palette_targets.targets import (
        get_recommended_target as _companion_get_recommended,
    )
except Exception:  # 附属插件未安装
    _companion_get_recommended = None


def get_recommended_target() -> dict[str, Any] | None:
    """返回推荐 Dashboard 目标 dict；失败返回 None。"""
    if _companion_get_recommended is not None:
        try:
            t = _companion_get_recommended()
            if t:
                return t
        except Exception:
            pass
    # 回退：data/dist（最常用路径）
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        dist = Path(get_astrbot_data_path()) / "dist"
        if dist.exists():
            return {
                "dist": str(dist),
                "index": str(dist / "index.html"),
                "source": "data/dist",
                "compatible": None,
                "restart_required": False,
                "fallback_target": "",
            }
    except Exception:
        pass
    return None


def get_dashboard_index() -> Path | None:
    """返回推荐 Dashboard 的 index.html 路径；不存在返回 None。"""
    t = get_recommended_target()
    if t:
        p = Path(t["index"])
        return p if p.exists() else None
    return None


def get_dashboard_dist() -> Path | None:
    """返回推荐 Dashboard 的 dist 目录；不存在返回 None。"""
    t = get_recommended_target()
    if t:
        p = Path(t["dist"])
        return p if p.exists() else None
    return None