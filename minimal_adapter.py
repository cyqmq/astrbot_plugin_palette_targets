"""最小接入器模板（其他插件复制本文件即可）。

设计原则：
- 附属插件 astrbot_plugin_palette_targets 持有完整的目标解析逻辑；
- 其他插件只内嵌这个「最小接入器」，不复制完整客户端；
- 接入器首选 import 附属插件 API，失败时仅回退到 data/dist 一次，
  避免每个插件都维护一大段解析代码。

用法一：获取 Dashboard 目标（目标发现/注入）：
    from minimal_adapter import get_dashboard_index

    index_path = get_dashboard_index()
    if index_path:
        content = index_path.read_text(encoding="utf-8")
        # ... 你的注入逻辑

用法二：注册调色盘毛玻璃代理路由（视图页面自动毛玻璃）：
    from minimal_adapter import register_palette_glass_proxy
    register_palette_glass_proxy(self.context, PLUGIN_NAME)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from astrbot.api.web import json_response

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


def _load_glass_api():
    """加载附属插件的毛玻璃 Python API；未安装返回 (None, None)。"""
    try:
        from data.plugins.astrbot_plugin_palette_targets.targets import (
            get_glass_css,
            get_background_data_url,
        )
        return get_glass_css, get_background_data_url
    except Exception:
        try:
            from astrbot_plugin_palette_targets.targets import (
                get_glass_css,
                get_background_data_url,
            )
            return get_glass_css, get_background_data_url
        except Exception:
            return None, None


def _load_glass_api():
    """加载附属插件的毛玻璃 Python API；未安装返回 (None, None, None)。"""
    try:
        from data.plugins.astrbot_plugin_palette_targets.targets import (
            get_glass_css,
            get_background_data_url,
            get_background_info,
        )
        return get_glass_css, get_background_data_url, get_background_info
    except Exception:
        try:
            from astrbot_plugin_palette_targets.targets import (
                get_glass_css,
                get_background_data_url,
                get_background_info,
            )
            return get_glass_css, get_background_data_url, get_background_info
        except Exception:
            return None, None, None


def register_palette_glass_proxy(context, plugin_name: str) -> None:
    """注册调色盘毛玻璃代理路由（最小接入器）。

    用法（在插件 __init__ 中调用，仅两行）：
        from minimal_adapter import register_palette_glass_proxy
        register_palette_glass_proxy(self.context, PLUGIN_NAME)

    效果：
    - 已安装 astrbot_plugin_palette_targets：插件的
      /<插件名>/glass.css 返回毛玻璃样式，/<插件名>/background-url
      返回调色盘壁纸 base64 data URL，/<插件名>/background-info
      返回背景名与主题色（轻量，供轮询检测变化）；
    - 未安装：全部返回空，插件保持原本外观，零影响。
    """
    prefix = f"/{plugin_name}"

    async def _glass_css():
        get_glass_css, _, _ = _load_glass_api()
        if get_glass_css is None:
            return json_response({"css": ""})
        try:
            return json_response({"css": get_glass_css()})
        except Exception:
            return json_response({"css": ""})

    async def _background_url():
        _, get_background_data_url, get_background_info = _load_glass_api()
        if get_background_data_url is None:
            return json_response({"url": "", "name": "", "theme": {"primary": "", "secondary": ""}})
        try:
            url = get_background_data_url()
            info = get_background_info() if get_background_info else {}
            return json_response(
                {
                    "url": url,
                    "name": info.get("name", ""),
                    "theme": info.get("theme", {"primary": "", "secondary": ""}),
                }
            )
        except Exception:
            return json_response({"url": "", "name": "", "theme": {"primary": "", "secondary": ""}})

    async def _background_info():
        _, _, get_background_info = _load_glass_api()
        if get_background_info is None:
            return json_response({"name": "", "theme": {"primary": "", "secondary": ""}})
        try:
            return json_response(get_background_info())
        except Exception:
            return json_response({"name": "", "theme": {"primary": "", "secondary": ""}})

    context.register_web_api(
        f"{prefix}/glass.css",
        _glass_css,
        ["GET"],
        "获取调色盘毛玻璃样式（代理 palette_targets）",
    )
    context.register_web_api(
        f"{prefix}/background-url",
        _background_url,
        ["GET"],
        "获取调色盘背景图 data URL（代理 palette_targets）",
    )
    context.register_web_api(
        f"{prefix}/background-info",
        _background_info,
        ["GET"],
        "获取调色盘背景名与主题色（代理 palette_targets）",
    )