# astrbot_plugin_palette_targets

AstrBot 调色盘目标发现附属插件：集中发现 AstrBot Dashboard 入口
（`data/dist`、AstrBot 内置 dist、自定义 `--webui-dir`），并暴露 API
供 `astrbot_plugin_palette` 主插件调用，避免主插件硬编码
`data/dist/index.html`。

## 完整安装流程

本插件是 `astrbot_plugin_palette` 的附属插件。要让它生效，需要：

1. **先安装主插件** `astrbot_plugin_palette`
2. **再安装本附属插件**
3. **给主插件打接入补丁**（关键步骤，否则主插件不会调用本插件）

### 第 1 步：安装主插件

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/Sisyphbaous-DT-Project/astrbot_plugin_palette.git
```

在 AstrBot WebUI「插件」页重载/刷新插件，确认 `AstrBot调色盘` 出现。

### 第 2 步：安装本附属插件

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/cyqmq/astrbot_plugin_palette_targets.git
```

在 AstrBot WebUI「插件」页重载插件，确认 `AstrBot 调色盘目标发现` 出现。

### 第 3 步：给主插件打补丁

打开 `data/plugins/astrbot_plugin_palette/palette/injector.py`，按下方
「主插件接入方式」修改 `_resolve_dashboard_target()`：优先调用本附属插件的
Python API 获取推荐目标；未安装本插件时自动回退到原逻辑。保存后在 AstrBot
中重载主插件。

### 常见问题

| 问题 | 答案 |
|---|---|
| 不装本附属插件，主插件能用吗？ | 能，主插件走原有内部逻辑（补丁里的 `except ImportError` 回退） |
| 不打补丁，装本附属插件有效吗？ | 无效，主插件不会调用它 |
| 本插件要先于主插件安装吗？ | 不需要，补丁运行时才 import，后装也行 |
| 需要重启 AstrBot 吗？ | 重载插件即可 |
| 如何验证生效？ | 浏览器访问 `.../astrbot_plugin_palette_targets/dashboard-targets`，能返回目标 JSON 即正常 |

## 安装（仅附属插件本身）

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/cyqmq/astrbot_plugin_palette_targets.git
```

然后在 AstrBot WebUI 中重载插件。

## 暴露的 API

### HTTP API（需要浏览器会话 Cookie）

```
GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets
GET /api/v1/plugins/extensions/astrbot_plugin_palette_targets/dashboard-targets/recommended
```

返回：
```json
{
  "code": 0,
  "data": {
    "targets": [
      {
        "dist": "/path/to/AstrBot/data/dist",
        "index": "/path/to/AstrBot/data/dist/index.html",
        "source": "data/dist",
        "compatible": true,
        "restart_required": false,
        "fallback_target": ""
      }
    ]
  }
}
```

### Python API（同进程插件直接 import）

```python
from astrbot_plugin_palette_targets.targets import (
    get_dashboard_targets,
    get_recommended_target,
)

targets = get_dashboard_targets()          # list[dict]
target = get_recommended_target()           # dict | None
```

## 主插件（astrbot_plugin_palette）接入方式

在 palette 的 `palette/injector.py` 的 `_resolve_dashboard_target` 中，
优先调用本附属插件的 Python API；未安装时回退到原有内部逻辑：

```python
try:
    from astrbot_plugin_palette_targets.targets import get_recommended_target
except ImportError:
    get_recommended_target = None

def _resolve_dashboard_target(paths, *, allow_copy_fallback):
    if get_recommended_target is not None:
        try:
            target = get_recommended_target()
            if target:
                from .injector import DashboardTarget  # 或复用已有 dataclass
                return DashboardTarget(
                    dist=Path(target["dist"]),
                    index=Path(target["index"]),
                    source=target["source"],
                    compatible=target["compatible"],
                    restart_required=target.get("restart_required", False),
                    fallback_target=target.get("fallback_target", ""),
                )
        except Exception:
            pass
    # 回退：原有内部解析逻辑
    ...
```

## 说明

- 本插件不修改任何 AstrBot 文件，只做「目标发现」，注入逻辑仍在主插件。
- 若 AstrBot 核心 API（`resolve_dashboard_dist` 等）在旧版本缺失，会自动回退
  到 4.26.x 兼容逻辑或仅返回 `data/dist`。
- 可选查询参数 `webui_dir` 可覆盖自定义 dist（调试用）。