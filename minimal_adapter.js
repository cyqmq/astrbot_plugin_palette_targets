/*
 * minimal_adapter.js — AstrBot 调色盘毛玻璃最小接入器（约 45 行）。
 *
 * 用法：复制本文件到你的插件 <views>/<视图名>/ 目录，然后在 index.html 中引入：
 *   <script src="./minimal_adapter.js"></script>
 *
 * 行为：
 *   - 已安装 astrbot_plugin_palette_targets：
 *       1. 注入通用毛玻璃样式（glass.css），卡片/输入框半透明 + backdrop-filter；
 *       2. 获取调色盘当前背景图 URL 并设置为页面 body 背景，
 *          让毛玻璃卡片在 iframe 内真正模糊壁纸。
 *   - 未安装该附属插件：请求在父页面侧返回错误，静默失败，
 *      页面保持插件原本外观，零影响。
 *
 * 实现说明：
 *   插件视图 iframe 的 origin 为 null（sandbox 隔离），直接 fetch 会触发
 *   CORS preflight 且无法携带登录态。因此本接入器通过 AstrBot 官方 bridge
 *   （window.AstrBotPluginView.apiGet）让父页面（已登录）代理 API 请求。
 */
(function () {
  "use strict";

  var GLASS_ENDPOINT =
    "plugins/extensions/astrbot_plugin_palette_targets/glass.css";
  var BACKGROUND_ENDPOINT =
    "plugins/extensions/astrbot_plugin_palette_targets/background-url";
  var STYLE_ID = "astrbot-palette-glass";

  function injectGlass(css) {
    if (!css || document.getElementById(STYLE_ID)) {
      return;
    }
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
  }

  function applyBackground(url) {
    if (!url || !document.body) {
      return;
    }
    document.body.style.backgroundImage = 'url("' + url + '")';
    document.body.style.backgroundSize = "cover";
    document.body.style.backgroundPosition = "center center";
    document.body.style.backgroundAttachment = "fixed";
    document.body.style.backgroundColor = "transparent";
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

  whenBridge().then(function (bridge) {
    if (!bridge) {
      // 非 AstrBot 插件视图环境：保持插件原样
      return;
    }
    bridge
      .apiGet(GLASS_ENDPOINT)
      .then(function (data) {
        injectGlass(data && data.css);
      })
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
    bridge
      .apiGet(BACKGROUND_ENDPOINT)
      .then(function (data) {
        applyBackground(data && data.url);
      })
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
  });
})();