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
 *   - 获取调色盘当前背景图（base64 data URL）与主题色，设置为页面背景和
 *     CSS 变量；
 *   - 每 10 秒轮询 background-info + 页面重新可见时检测：调色盘背景/主题
 *     变化后自动刷新，毛玻璃效果跟随调色盘配置；
 *   - 未安装 astrbot_plugin_palette_targets：请求返回空值，静默失败，
 *     页面保持插件原本外观，零影响。
 */
(function () {
  "use strict";

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

  function setThemeVars(theme) {
    var de = document.documentElement;
    if (!theme) {
      return;
    }
    if (theme.primary) {
      de.style.setProperty("--v-theme-primary", theme.primary);
    }
    if (theme.secondary) {
      de.style.setProperty("--v-theme-secondary", theme.secondary);
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
    setThemeVars(data.theme);
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
    // 恢复可见：立即检测一次（主插件同款行为），再恢复兜底轮询。
    checkAndRefresh().then(schedulePoll);
  }

  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("focus", function () {
    if (!document.hidden) {
      checkAndRefresh().then(schedulePoll);
    }
  });

  // 主文档桥接脚本（bridge.js）转发的配置变化广播。
  window.addEventListener("message", function (event) {
    var msg = event.data;
    if (msg && msg.channel === "astrbot-palette-targets") {
      if (msg.kind === "refresh") {
        // 收到广播：关闭自动轮询，事件驱动接管，立即刷新。
        eventDriven = true;
        if (pollTimer) {
          clearTimeout(pollTimer);
          pollTimer = null;
        }
        loadBackground();
      }
    }
  });

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
  });
})();