"""自动给主插件 astrbot_plugin_palette 打接入补丁（幂等）。

安装本附属插件后，无需手动编辑主插件文件：启动时检测
data/plugins/astrbot_plugin_palette/palette/injector.py，
若未包含对附属插件的调用则自动插入（与 README 手动补丁完全一致），
已打过补丁则跳过；主插件升级覆盖后会自动重新补丁。

安全策略：
- 仅在锚点完全匹配时插入，任何异常/结构变化都跳过，绝不破坏主插件；
- 写回前先备份原文件到本插件数据目录。
"""
from __future__ import annotations

import time
from pathlib import Path

_PATCH_MARKER = "astrbot_plugin_palette_targets.targets import"

_IMPORT_BLOCK = """
try:
    # 附属插件 astrbot_plugin_palette_targets 提供的目标发现 API（自动补丁）
    from data.plugins.astrbot_plugin_palette_targets.targets import (
        get_dashboard_targets,
        get_recommended_target,
    )
except Exception:  # pragma: no cover - 未安装附属插件时回退内部逻辑
    try:
        from astrbot_plugin_palette_targets.targets import (
            get_dashboard_targets,
            get_recommended_target,
        )
    except Exception:
        get_dashboard_targets = None
        get_recommended_target = None

"""

_FUNC_PATCH = """    # 优先调用附属插件暴露的 API 获取推荐目标（自动补丁）
    if get_recommended_target is not None:
        try:
            rec = get_recommended_target()
            if rec is not None:
                return DashboardTarget(
                    dist=Path(rec["dist"]),
                    index=Path(rec["index"]),
                    source=rec["source"],
                    compatible=rec["compatible"],
                    restart_required=bool(rec.get("restart_required", False)),
                    fallback_target=rec.get("fallback_target", "") or "",
                )
        except Exception:
            pass

"""


def _injector_path() -> Path | None:
    """定位主插件 injector.py。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
    except Exception:
        return None
    return (
        Path(get_astrbot_data_path())
        / "plugins"
        / "astrbot_plugin_palette"
        / "palette"
        / "injector.py"
    )


def _backup(path: Path) -> None:
    """写回前备份原文件到本插件数据目录。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        backup_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_palette_targets"
            / "patches"
        )
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = backup_dir / f"injector-{stamp}.py"
        if not target.exists():
            target.write_bytes(path.read_bytes())
    except Exception:
        pass


def ensure_palette_patch() -> bool:
    """检测并自动给主插件打补丁；返回 True 表示补丁已就绪。"""
    injector = _injector_path()
    if injector is None or not injector.is_file():
        return False
    try:
        content = injector.read_text(encoding="utf-8")
    except OSError:
        return False

    # 已打过补丁（无论手动还是自动）：跳过
    if _PATCH_MARKER in content:
        return True

    # 1. 插入可选导入（锚点：模块级 `_PREPARED_FALLBACK_DISTS`）
    anchor = "_PREPARED_FALLBACK_DISTS: set[str] = set()"
    if anchor not in content:
        return False
    content = content.replace(anchor, _IMPORT_BLOCK + anchor, 1)

    # 2. 在 `_resolve_dashboard_target` 函数体开头插入优先分支
    marker = "    custom_dist = _custom_dashboard_dist()"
    idx = content.find(marker)
    if idx == -1:
        return False
    prefix = content[:idx]
    if prefix.rfind("def _resolve_dashboard_target(") == -1:
        return False
    content = content[:idx] + _FUNC_PATCH + content[idx:]

    # 3. 备份并写回
    _backup(injector)
    try:
        temp = injector.with_suffix(injector.suffix + ".palette-targets.tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(injector)
        return True
    except OSError:
        return False