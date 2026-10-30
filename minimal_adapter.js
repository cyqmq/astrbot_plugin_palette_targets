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

  // 父页面 apiGet 会自动拼接当前插件的扩展路由前缀
  // （/api/v1/plugins/extensions/<当前插件>/<endpoint>），
  // 因此这里传相对路径，由宿主插件注册同名代理路由。
  var GLASS_ENDPOINT = "glass.css";
  var BACKGROUND_ENDPOINT = "background-url";
  var STYLE_ID = "astrbot-palette-glass";

  function injectGlass(css) {
    if (!css || document.getElementById(STYLE_ID)) {
      console.warn("[palette-adapter] glass.css 为空或已注入，跳过");
      return;
    }
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
    document.documentElement.setAttribute("data-palette-glass", "1");
    console.log("[palette-adapter] 毛玻璃样式已注入，长度:", css.length);
  }

  function applyBackground(url) {
    if (!url || !document.body) {
      console.warn("[palette-adapter] 背景 URL 为空，跳过");
      return;
    }
    document.body.style.backgroundImage = 'url("' + url + '")';
    document.body.style.backgroundSize = "cover";
    document.body.style.backgroundPosition = "center center";
    document.body.style.backgroundAttachment = "fixed";
    document.body.style.backgroundColor = "transparent";
    document.documentElement.setAttribute("data-palette-bg", "1");
    console.log("[palette-adapter] 背景已设置，前缀:", String(url).slice(0, 30));
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
      console.warn("[palette-adapter] AstrBotPluginView bridge 不可用，保持插件原样");
      return;
    }
    console.log("[palette-adapter] bridge 就绪，开始请求毛玻璃样式");
    bridge
      .apiGet(GLASS_ENDPOINT)
      .then(function (data) {
        injectGlass(data && data.css);
      })
      .catch(function (err) {
        console.warn("[palette-adapter] 获取毛玻璃样式失败:", err && err.message);
      });
    bridge
      .apiGet(BACKGROUND_ENDPOINT)
      .then(function (data) {
        applyBackground(data && data.url);
      })
      .catch(function (err) {
        console.warn("[palette-adapter] 获取背景失败:", err && err.message);
      });
  });
})();