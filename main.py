"""AstrBot 调色盘目标发现插件。

供 astrbot_plugin_palette 调用：
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets
  返回候选 Dashboard 目标列表（JSON）。
- Python API：from astrbot_plugin_palette_targets.targets import (
                  get_dashboard_targets, get_recommended_target)

还提供「毛玻璃注入」能力，供其他插件视图自动适配调色盘壁纸：
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/glass.css
  返回通用毛玻璃样式。
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/background-url
  返回调色盘当前背景图 URL（iframe 内同步壁纸用）。
- 其他插件只需在视图 index.html 引入 minimal_adapter.js（约 20 行），
  有本插件时自动注入毛玻璃并同步壁纸，没有时保持插件原本外观。
"""
from __future__ import annotations

import json
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, register
from astrbot.api.web import json_response, request, stream_response

from .targets import get_dashboard_targets, get_recommended_target

PLUGIN_NAME = "astrbot_plugin_palette_targets"
ROUTE_PREFIX = f"/{PLUGIN_NAME}"

_GLASS_CSS = (
    Path(__file__).with_name("glass.css").read_text(encoding="utf-8")
)

_PALETTE_BACKGROUNDS_ROUTE = (
    "/api/v1/plugins/extensions/astrbot_plugin_palette/backgrounds"
)


def _palette_config_path() -> Path | None:
    """定位调色盘主插件配置文件。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        return Path(get_astrbot_data_path()) / "config" / "astrbot_plugin_palette_config.json"
    except Exception:
        return None


def _palette_background_url() -> str:
    """读取调色盘当前背景图，返回可被 iframe 直接使用的 URL。

    返回空串表示调色盘未配置背景或读取失败。
    """
    try:
        path = _palette_config_path()
        if path is None or not path.exists():
            return ""
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
        name = (
            cfg.get("landscape_background_image")
            or cfg.get("background_image")
            or (cfg.get("landscape_background_images") or [None])[0]
            or cfg.get("portrait_background_image")
            or (cfg.get("portrait_background_images") or [None])[0]
            or ""
        )
        if not name:
            return ""
        if name.startswith("http://") or name.startswith("https://"):
            return name
        if name.startswith("/"):
            return name
        return f"{_PALETTE_BACKGROUNDS_ROUTE}/{name}"
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
        """返回通用毛玻璃样式表（text/css）。

        其他插件的 minimal_adapter.js 请求本接口，成功则注入样式，
        失败（本插件未安装）则保持插件原本外观。
        """
        return stream_response(
            [_GLASS_CSS],
            content_type="text/css; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    async def background_url(self):
        """返回调色盘当前背景图 URL（JSON）。

        iframe 内的 minimal_adapter.js 请求本接口，将背景图同步到
        插件视图页面，使毛玻璃卡片能够模糊壁纸（iframe 内
        backdrop-filter 无法跨文档模糊父页面壁纸，必须自绘背景）。
        """
        try:
            return json_response({"url": _palette_background_url()})
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