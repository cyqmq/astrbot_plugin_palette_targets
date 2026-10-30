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
- HTTP API：GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/bridge.js
  主文档桥接脚本（监听调色盘配置广播并转发给插件视图 iframe）。
- 其他插件只需在视图 index.html 引入 minimal_adapter.js（约 45 行），
  有本插件时自动注入毛玻璃并同步壁纸，没有时保持插件原本外观。
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.star import Context, Star, register
from astrbot.api.web import json_response, request, stream_response

from .targets import (
    get_background_data_url,
    get_dashboard_targets,
    get_glass_css,
    get_palette_theme,
    get_recommended_target,
)
from .auto_patch import ensure_palette_patch

PLUGIN_NAME = "astrbot_plugin_palette_targets"
ROUTE_PREFIX = f"/{PLUGIN_NAME}"

_GLASS_CSS = (
    Path(__file__).with_name("glass.css").read_text(encoding="utf-8")
)

_BRIDGE_JS = (
    Path(__file__).with_name("bridge.js").read_text(encoding="utf-8")
)

_INJECTION_START_MARKER = "<!-- astrbot_plugin_palette_targets:start -->"
_INJECTION_END_MARKER = "<!-- astrbot_plugin_palette_targets:end -->"


def ensure_bridge_injection() -> bool:
    """向 AstrBot dashboard 主文档幂等注入桥接脚本。

    桥接脚本监听调色盘主插件的 BroadcastChannel / storage 广播，
    并把配置变化转发给页面内的插件视图 iframe，使 minimal_adapter
    无需轮询即可实时刷新。注入失败（无 data/dist 等）静默跳过，
    不影响其他功能。
    """
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        index = Path(get_astrbot_data_path()) / "dist" / "index.html"
        if not index.is_file():
            return False
        content = index.read_text(encoding="utf-8")
        if _INJECTION_START_MARKER in content and _INJECTION_END_MARKER in content:
            return True
        head_close = re.search(r"</head\s*>", content, flags=re.IGNORECASE)
        if head_close is None:
            return False
        block = (
            "\n  " + _INJECTION_START_MARKER + "\n"
            '  <script src="/api/v1/plugins/extensions/astrbot_plugin_palette_targets/bridge.js"></script>\n'
            + "  " + _INJECTION_END_MARKER + "\n"
        )
        next_content = content[: head_close.start()] + block + content[head_close.start():]
        temp = index.with_suffix(index.suffix + ".palette-targets.tmp")
        temp.write_text(next_content, encoding="utf-8")
        temp.replace(index)
        return True
    except Exception:
        return False

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
            f"{ROUTE_PREFIX}/bridge.js",
            self.bridge_js,
            ["GET"],
            "主文档桥接脚本（监听调色盘配置广播并转发给插件视图 iframe）",
        )
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
        context.register_web_api(
            f"{ROUTE_PREFIX}/background-info",
            self.background_info,
            ["GET"],
            "获取调色盘背景名与主题色（轻量，供检测变化）",
        )
        # 自动给主插件 palette 打接入补丁（幂等，省去手动编辑）
        ensure_palette_patch()
        ensure_bridge_injection()

    async def bridge_js(self):
        """返回主文档桥接脚本（text/javascript）。"""
        return stream_response(
            [_BRIDGE_JS],
            content_type="text/javascript; charset=utf-8",
            headers={"Cache-Control": "no-store"},
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
        """返回调色盘当前背景图 data URL 与主题色（JSON）。

        iframe 内无法直接加载需要鉴权的背景图 URL，因此后端读取
        背景文件并转为 base64 data URL，minimal_adapter 将其设置为
        页面背景，使毛玻璃卡片能够模糊壁纸。
        """
        try:
            return json_response(
                {
                    "url": get_background_data_url(),
                    "name": _palette_background_name(),
                    "theme": get_palette_theme(),
                }
            )
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 读取调色盘背景失败: {e}")
            return json_response({"url": "", "name": "", "theme": {"primary": "", "secondary": ""}})

    async def background_info(self):
        """返回调色盘当前背景名与主题色（轻量 JSON，不含 base64）。

        minimal_adapter 定期轮询本接口检测变化，只有变化时才重新
        请求 background-url，避免频繁传输大体积 base64。
        """
        try:
            return json_response(
                {
                    "name": _palette_background_name(),
                    "theme": get_palette_theme(),
                }
            )
        except Exception as e:
            logger.error(f"[{PLUGIN_NAME}] 读取调色盘背景信息失败: {e}")
            return json_response({"name": "", "theme": {"primary": "", "secondary": ""}})

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