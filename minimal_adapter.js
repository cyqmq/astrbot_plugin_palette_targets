/*
 * minimal_adapter.js — AstrBot 调色盘毛玻璃最小接入器。
 *
 * 用法：复制本文件到你的插件 <views>/<视图名>/ 目录，然后在 index.html 中引入：
 *   <script src="./minimal_adapter.js"></script>
 * 同时插件需复制 minimal_adapter.py 并在 main.py 中调用
 *   register_palette_glass_proxy(self.context, PLUGIN_NAME)
 *
 * 行为：
 *   - 注入通用毛玻璃样式（glass.css），卡片/输入框半透明 + backdrop-filter；
 *   - 获取调色盘当前背景图（base64 data URL）设置为页面背景；
 *   - 通过主文档桥接脚本（bridge.js）读取与原版 UI 完全一致的 Vuetify
 *     主题 CSS 变量（--v-theme-surface / on-surface / primary 等），
 *     应用到 iframe 内，使毛玻璃效果与原版一致并跟随调色盘配置；
 *   - 事件驱动：主文档桥接脚本转发调色盘配置变化广播后立即刷新，
 *     并关闭自动轮询；
 *   - 未安装 astrbot_plugin_palette_targets 或 bridge 不可用时，
 *     请求返回空值/静默失败，页面保持插件原本外观，零影响。
 */
(function () {
  "use strict";

  var MSG_CHANNEL = "astrbot-palette-targets";
  var GLASS_ENDPOINT = "glass.css";
  var BACKGROUND_ENDPOINT = "background-url";
  var INFO_ENDPOINT = "background-info";
  var STYLE_ID = "astrbot-palette-glass";
  // 仅页面可见时轮询（轻量 background-info，几字节）；隐藏时零请求。
  var POLL_INTERVAL_MS = 30000;

  var current = { name: "", primary: "", secondary: "" };
  var pollTimer = null;
  // 收到主文档桥接脚本转发的广播后置为 true，关闭自动轮询（事件驱动）。
  var eventDriven = false;

  var THEME_VAR_MAP = {
    primary: "--v-theme-primary",
    secondary: "--v-theme-secondary",
    darkprimary: "--v-theme-darkprimary",
    darksecondary: "--v-theme-darksecondary",
    surface: "--v-theme-surface",
    onSurface: "--v-theme-on-surface",
    background: "--v-theme-background",
    onBackground: "--v-theme-on-background",
    containerBg: "--v-theme-containerBg",
  };

  function applyThemeVars(theme) {
    var de = document.documentElement;
    if (!theme) {
      return;
    }
    for (var key in THEME_VAR_MAP) {
      if (theme[key]) {
        de.style.setProperty(THEME_VAR_MAP[key], theme[key]);
      }
    }
  }

  function injectGlass(css) {
    if (!css || document.getElementById(STYLE_ID)) {
      return;
    }
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
    document.documentElement.setAttribute("data-palette-glass", "1");
  }

  function applyBackground(data) {
    if (!data || !data.url || !document.body) {
      return;
    }
    document.body.style.backgroundImage = 'url("' + data.url + '")';
    document.body.style.backgroundSize = "cover";
    document.body.style.backgroundPosition = "center center";
    document.body.style.backgroundAttachment = "fixed";
    document.body.style.backgroundColor = "transparent";
    applyThemeVars(data.theme);
    current.name = data.name || "";
    current.primary = (data.theme && data.theme.primary) || "";
    current.secondary = (data.theme && data.theme.secondary) || "";
    document.documentElement.setAttribute("data-palette-bg", "1");
  }

  function whenBridge() {
    return new Promise(function (resolve) {
      if (window.AstrBotPluginView) {
        return resolve(window.AstrBotPluginView);
      }
      var timer = setInterval(function () {
        if (window.AstrBotPluginView) {
          clearInterval(timer);
          resolve(window.AstrBotPluginView);
        }
      }, 50);
      setTimeout(function () {
        clearInterval(timer);
        resolve(window.AstrBotPluginView || null);
      }, 3000);
    });
  }

  function apiGet(endpoint) {
    return whenBridge().then(function (bridge) {
      if (!bridge) {
        throw new Error("bridge not available");
      }
      return bridge.apiGet(endpoint);
    });
  }

  function hasChanged(info) {
    if (!info) {
      return false;
    }
    var theme = info.theme || {};
    return (
      (info.name || "") !== current.name ||
      (theme.primary || "") !== current.primary ||
      (theme.secondary || "") !== current.secondary
    );
  }

  function loadBackground() {
    return apiGet(BACKGROUND_ENDPOINT)
      .then(function (data) {
        applyBackground(data);
      })
      .catch(function () {
        /* 无附属插件或未登录：保持插件原样 */
      });
  }

  function checkAndRefresh() {
    return apiGet(INFO_ENDPOINT)
      .then(function (info) {
        if (hasChanged(info)) {
          return loadBackground();
        }
      })
      .catch(function () {
        /* 保持插件原样 */
      });
  }

  function requestThemeFromParent() {
    // 向主文档桥接脚本请求与原版 UI 一致的主题 CSS 变量。
    try {
      window.parent.postMessage(
        { channel: MSG_CHANNEL, kind: "get-theme" },
        "*"
      );
    } catch (e) {
      /* 忽略 */
    }
  }

  function handleParentMessage(event) {
    var msg = event.data;
    if (!msg || msg.channel !== MSG_CHANNEL) {
      return;
    }
    if (msg.kind === "theme" && msg.theme) {
      applyThemeVars(msg.theme);
    } else if (msg.kind === "refresh") {
      // 收到广播：关闭自动轮询，事件驱动接管，立即刷新并重新读取主题。
      eventDriven = true;
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
      loadBackground();
      requestThemeFromParent();
    }
  }

  function schedulePoll() {
    // 页面隐藏时或不轮询（事件驱动已接管）：跳过。
    if (document.hidden || eventDriven) {
      return;
    }
    if (pollTimer) {
      clearTimeout(pollTimer);
    }
    pollTimer = setTimeout(function poll() {
      checkAndRefresh().then(function () {
        // 每次轮询顺带刷新原版主题变量（轻量 postMessage）。
        requestThemeFromParent();
        if (!document.hidden) {
          pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
        } else {
          pollTimer = null;
        }
      });
    }, POLL_INTERVAL_MS);
  }

  function onVisibilityChange() {
    if (document.hidden) {
      if (pollTimer) {
        clearTimeout(pollTimer);
        pollTimer = null;
      }
      return;
    }
    // 恢复可见：立即检测背景变化并刷新主题变量，再恢复兜底轮询。
    checkAndRefresh().then(schedulePoll);
    requestThemeFromParent();
  }

  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("focus", function () {
    if (!document.hidden) {
      checkAndRefresh().then(schedulePoll);
      requestThemeFromParent();
    }
  });

  // 主文档桥接脚本（bridge.js）的响应与广播。
  window.addEventListener("message", handleParentMessage);

  whenBridge().then(function (bridge) {
    if (!bridge) {
      // 非 AstrBot 插件视图环境：保持插件原样
      return;
    }
    apiGet(GLASS_ENDPOINT)
      .then(function (data) {
        injectGlass(data && data.css);
      })
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
    loadBackground().then(schedulePoll);
    requestThemeFromParent();
  });
})();