"""AstrBot 调色盘目标发现插件。

供 astrbot_plugin_palette 调用：
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets
  返回候选 Dashboard 目标列表（JSON）。
- Python API：from astrbot_plugin_palette_targets.targets import (
                  get_dashboard_targets, get_recommended_target)

这样主插件不再需要硬编码 data/dist/index.html 的解析逻辑。
"""
from __future__ import annotations

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, register
from astrbot.api.web import json_response, request

from .targets import get_dashboard_targets, get_recommended_target

PLUGIN_NAME = "astrbot_plugin_palette_targets"
ROUTE_PREFIX = f"/{PLUGIN_NAME}"


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