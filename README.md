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

## 其他插件接入（适配逻辑）

推荐方案：**附属插件持有全部解析逻辑，其他插件只内嵌一个最小接入器**，
避免每个插件复制完整客户端导致臃肿。

### 方式 C（推荐）：毛玻璃自动注入（只插入最小连接器）

如果你的插件有**视图页面**（`views/<视图名>/index.html`，AstrBot 以 iframe
加载），想让页面透出调色盘壁纸（卡片半透明 + 毛玻璃），只需复制
**两个文件**并做 **3 行修改**：

**第 1 步：复制最小接入器**

```bash
# 前端接入器（约 45 行 JS）→ 视图目录
cp .../astrbot_plugin_palette_targets/minimal_adapter.js \
   <你的插件>/views/<视图名>/minimal_adapter.js

# 后端接入器（约 100 行 Python，含代理路由注册）→ 插件根目录
cp .../astrbot_plugin_palette_targets/minimal_adapter.py \
   <你的插件>/minimal_adapter.py
```

**第 2 步：视图入口引入 JS**

在 `<你的插件>/views/<视图名>/index.html` 的 `</body>` 前加一行：

```html
<script src="./minimal_adapter.js"></script>
```

**第 3 步：插件 main.py 注册代理路由（两行）**

在插件类的 `__init__` 中（已有 `self.context`）加：

```python
from .minimal_adapter import register_palette_glass_proxy

register_palette_glass_proxy(self.context, PLUGIN_NAME)
```

`PLUGIN_NAME` 是你的插件唯一标识名（与 `@register` 的第一个参数一致，
如 `astrbot_plugin_monkeycode`）。注意必须用**相对导入**（`from .minimal_adapter`），
因为 AstrBot 插件以 `data.plugins.<插件名>.main` 加载，`minimal_adapter.py`
与 `main.py` 同属一个包。

**为什么需要代理路由**：AstrBot 插件视图 iframe 的 `bridge.apiGet` 只会请求
**当前插件自己的扩展路由**（自动拼接 `/plugins/extensions/<当前插件>/`
前缀），无法跨插件调用。因此由宿主插件注册同名路由，后端通过
`minimal_adapter.py` 调用 `astrbot_plugin_palette_targets` 的 Python API
（未安装时返回空串）。

**行为**：
- **已安装 `astrbot_plugin_palette_targets`**：`minimal_adapter.js` 通过
  bridge 请求宿主插件的 `/glass.css` 与 `/background-url`，注入毛玻璃样式，
  并把调色盘壁纸（base64 data URL）设置为页面 body 背景，卡片半透明 +
  `backdrop-filter` 生效。
- **未安装本附属插件**：`minimal_adapter.py` 返回 `{"css":""}` / `{"url":""}`，
  接入器检测到空值后跳过，页面保持原本外观，零影响。

**配置变化同步策略**（低开销）：
- `minimal_adapter.js` 在**页面可见时**每 30 秒请求一次轻量
  `background-info`（几字节 JSON：背景名 + 主题色），检测到变化才重新
  拉取含 base64 的 `background-url`；
- 页面**隐藏时零请求**，恢复可见时立即检测并刷新（与调色盘主插件的
  `visibilitychange` 行为一致）；
- 两个标签页同时可见时，最长 30 秒内自动同步背景/主题变化。

`glass.css` 使用 CSS 变量 + fallback：
- 有 Vuetify 主题变量（`--v-theme-surface` 等）时跟随调色盘主题；
- 没有时按 `prefers-color-scheme` 自动退化浅色/深色默认值。

**已按此方式接入的插件**：`astrbot_plugin_monkeycode`（MonkeyCode 编程助手
的设置视图）。可参考其 `main.py`、`views/settings/` 目录作为实例。

### 方式 A（推荐）：Python 最小接入器，约 25 行

复制仓库里的 **`minimal_adapter.py`** 到你的插件目录，即可获得三个函数：

```python
from minimal_adapter import get_recommended_target, get_dashboard_index, get_dashboard_dist

target = get_recommended_target()   # dict | None
index = get_dashboard_index()       # Path | None（推荐 index.html）
dist  = get_dashboard_dist()        # Path | None
```

适配原理（两层）：
1. **首选**：`import astrbot_plugin_palette_targets.targets`
   - 附属插件已安装 → 完整解析（data/dist、bundled、--webui-dir、公开解析器）
2. **回退**：仅查 `data/dist` 一次（`get_astrbot_data_path() / "dist"`）
   - 附属插件未安装也能覆盖最常见路径

这样你的插件只多 25 行，重的解析逻辑全在附属插件里，多个插件共用一份。

### 方式 B（可选）：完整客户端

如果插件需要更多能力（目标列表、Path 对象、示例工具函数），
可复制 **`palette_targets_client.py`**（约 130 行），提供：
`get_dashboard_targets` / `get_recommended_target` / `get_dashboard_paths` /
`get_recommended_paths` / `ensure_index_writable`。

### 方式 D（可选）：astrbotui 原版 UI 库

如果你的插件视图是纯 HTML（没有 Vuetify），想让卡片、背景、输入框、按钮
等组件**长得像 AstrBot 原版 UI**，可以引入本仓库提供的 **`astrbotui.css`**：

```bash
cp .../astrbot_plugin_palette_targets/astrbotui.css \
   <你的插件>/views/<视图名>/astrbotui.css
```

在 `index.html` 的 `<head>` 中加入：

```html
<link rel="stylesheet" href="./astrbotui.css" />
```

特性：
- 内置 AstrBot 原版 PurpleThemeDark / PurpleTheme 的默认主题变量
  （`--v-theme-surface`、`--v-theme-on-surface`、`--v-theme-primary` 等），
  不使用调色盘/附属插件时样式也与原版高度一致；
- 组件样式基于同一套 `--v-theme-*` 变量，可被
  `minimal_adapter.js` + bridge.js 注入的实时主题变量直接覆盖，
  接入调色盘后毛玻璃效果与原版完全一致；
- 非强制：插件可以继续保留自己的 `style.css`，本库按需引入。

### 方式 E（进阶）：Vuetify 3 插件视图模板

如果希望插件设置页**本身就是 Vuetify 应用**，与原版 UI 完全一致（组件、
变量、主题切换原生同步），可以使用本仓库的 `webui/` 模板（参考
`astrbot_plugin_angel_memory` 的工程结构）：

```
webui/
├── package.json          # Vue 3 + Vuetify 3 + Vite
├── vite.config.js        # 构建输出到 ../pages/<页面名>/
├── index.html
└── src/
    ├── main.js           # createVuetify + data-theme 默认主题
    ├── App.vue           # 示例页面（MutationObserver 监听 data-theme 切换主题）
    └── composables/
        └── useBridge.js  # 封装 window.AstrBotPluginPage（含开发模式回退）
```

流程：
1. 复制 `webui/` 到你的插件目录，按需修改 `App.vue` 与 API 端点；
2. `npm install && npm run build`，产物输出到 `pages/<页面名>/`；
3. AstrBot 自动发现 `pages/` 下的目录为插件视图，加载时自动注入
   `/api/plugin/page/bridge-sdk.js`；
4. 页面内 `window.AstrBotPluginPage` 可用，主题通过
   `<html data-theme>` 与仪表盘实时同步（亮/暗主题自动切换）。

本仓库已包含构建好的示例页 `pages/vuetify-demo/`，安装本插件后可在
AstrBot 中打开「vuetify-demo」视图查看效果。

## 说明

- 本插件不修改任何 AstrBot 文件，只做「目标发现」，注入逻辑仍在主插件。
- 若 AstrBot 核心 API（`resolve_dashboard_dist` 等）在旧版本缺失，会自动回退
  到 4.26.x 兼容逻辑或仅返回 `data/dist`。
- 可选查询参数 `webui_dir` 可覆盖自定义 dist（调试用）。