"""AstrBot 调色盘目标发现插件。

供 astrbot_plugin_palette 调用：
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets
  返回候选 Dashboard 目标列表（JSON）。
- Python API：from astrbot_plugin_palette_targets.targets import (
                  get_dashboard_targets, get_recommended_target)

还提供「毛玻璃注入」能力，供其他插件视图自动适配调色盘壁纸：
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/glass.css
  返回通用毛玻璃样式（JSON：{"css": "..."}）。
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/background-url
  返回调色盘当前背景图（JSON：{"url": "data:image/...;base64,..."}）。
- 其他插件只需在视图 index.html 引入 minimal_adapter.js（约 45 行），
  有本插件时自动注入毛玻璃并同步壁纸，没有时保持插件原本外观。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, register
from astrbot.api.web import json_response, request

from .targets import get_dashboard_targets, get_recommended_target

PLUGIN_NAME = "astrbot_plugin_palette_targets"
ROUTE_PREFIX = f"/{PLUGIN_NAME}"

_GLASS_CSS = (
    Path(__file__).with_name("glass.css").read_text(encoding="utf-8")
)

_PALETTE_BACKGROUND_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


def _palette_config_path() -> Path | None:
    """定位调色盘主插件配置文件。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        return Path(get_astrbot_data_path()) / "config" / "astrbot_plugin_palette_config.json"
    except Exception:
        return None


def _palette_background_name() -> str:
    """读取调色盘当前背景文件名或 URL。"""
    try:
        path = _palette_config_path()
        if path is None or not path.exists():
            return ""
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
        return (
            cfg.get("landscape_background_image")
            or cfg.get("background_image")
            or (cfg.get("landscape_background_images") or [None])[0]
            or cfg.get("portrait_background_image")
            or (cfg.get("portrait_background_images") or [None])[0]
            or ""
        )
    except Exception:
        return ""


def _palette_background_data_url() -> str:
    """读取调色盘当前背景图，返回可直接用作 CSS 背景的 data URL。

    背景图接口需要登录鉴权，iframe 内无法通过 <img>/CSS 背景携带
    Authorization，因此这里由后端读取文件并转为 base64 data URL，
    交给 minimal_adapter 作为页面背景。
    """
    try:
        name = _palette_background_name()
        if not name:
            return ""
        if name.startswith("http://") or name.startswith("https://") or name.startswith("data:"):
            return name
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        bg_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_palette"
            / "backgrounds"
        )
        fpath = bg_dir / name
        if not fpath.exists():
            return ""
        mime = _PALETTE_BACKGROUND_MIME.get(fpath.suffix.lower(), "application/octet-stream")
        b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


@register(
    "astrbot_plugin_palette_targets",
    "cyqmq",
    "AstrBot 调色盘目标发现：集中暴露 Dashboard 入口列表，供调色盘主插件调用",
    "0.1.0",
)
class PaletteTargetsPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        context.register_web_api(
            f"{ROUTE_PREFIX}/dashboard-targets",
            self.dashboard_targets,
            ["GET"],
            "获取 AstrBot Dashboard 候选入口列表",
        )
        context.register_web_api(
            f"{ROUTE_PREFIX}/dashboard-targets/recommended",
            self.dashboard_recommended,
            ["GET"],
            "获取 AstrBot Dashboard 推荐入口",
        )
        context.register_web_api(
            f"{ROUTE_PREFIX}/glass.css",
            self.glass_css,
            ["GET"],
            "获取通用毛玻璃样式（供其他插件视图注入）",
        )
        context.register_web_api(
            f"{ROUTE_PREFIX}/background-url",
            self.background_url,
            ["GET"],
            "获取调色盘当前背景图 URL（供插件视图同步壁纸）",
        )

    async def glass_css(self):
        """返回通用毛玻璃样式（JSON）。

        父页面 bridge 使用 axios 代理请求，对 text/css 响应会按 JSON
        解析而失败，因此这里返回 {"css": "..."}。
        """
        try:
            return json_response({"css": _GLASS_CSS})
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 返回毛玻璃样式失败: {e}")
            return json_response({"css": ""})

    async def background_url(self):
        """返回调色盘当前背景图 data URL（JSON）。

        iframe 内无法直接加载需要鉴权的背景图 URL，因此后端读取
        背景文件并转为 base64 data URL，minimal_adapter 将其设置为
        页面背景，使毛玻璃卡片能够模糊壁纸。
        """
        try:
            return json_response({"url": _palette_background_data_url()})
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 读取调色盘背景失败: {e}")
            return json_response({"url": ""})

    async def dashboard_targets(self):
        """返回全部候选 Dashboard 目标。"""
        custom_dist = request.query.get("webui_dir") or None
        try:
            return json_response(
                {
                    "targets": get_dashboard_targets(custom_dist),
                    "error": None,
                }
            )
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 发现 Dashboard 目标失败: {e}")
            return json_response(
                {"targets": [], "error": str(e)}
            )

    async def dashboard_recommended(self):
        """返回推荐使用的 Dashboard 目标。"""
        custom_dist = request.query.get("webui_dir") or None
        try:
            return json_response(
                {"target": get_recommended_target(custom_dist), "error": None}
            )
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 发现推荐目标失败: {e}")
            return json_response(
                {"target": None, "error": str(e)}
            )

    async def terminate(self):
        pass