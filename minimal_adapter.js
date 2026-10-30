/*
 * minimal_adapter.js — AstrBot 调色盘毛玻璃最小接入器（约 40 行）。
 *
 * 用法：复制本文件到你的插件 <views>/<视图名>/ 目录，然后在 index.html 中引入：
 *   <script src="./minimal_adapter.js"></script>
 *
 * 行为：
 *   - 已安装 astrbot_plugin_palette_targets：
 *       1. 注入通用毛玻璃样式（glass.css），卡片/输入框半透明 + backdrop-filter；
 *       2. 获取调色盘当前背景图 URL 并设置为页面 body 背景，
 *          让毛玻璃卡片在 iframe 内真正模糊壁纸。
 *   - 未安装该附属插件：请求返回非目标 content-type，静默失败，
 *      页面保持插件原本外观，零影响。
 */
(function () {
  "use strict";

  var BASE_URL = "/api/v1/plugins/extensions/astrbot_plugin_palette_targets";
  var GLASS_CSS_URL = BASE_URL + "/glass.css";
  var BACKGROUND_URL_URL = BASE_URL + "/background-url";
  var STYLE_ID = "astrbot-palette-glass";

  function isContentType(resp, prefix) {
    var type = (resp.headers.get("content-type") || "").toLowerCase();
    return resp.ok && type.indexOf(prefix) === 0;
  }

  function injectGlass(css) {
    if (document.getElementById(STYLE_ID)) {
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

  function requestGlass() {
    fetch(GLASS_CSS_URL, { cache: "no-cache" })
      .then(function (resp) {
        if (!isContentType(resp, "text/css")) {
          throw new Error("companion plugin not available");
        }
        return resp.text();
      })
      .then(injectGlass)
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
  }

  function requestBackground() {
    fetch(BACKGROUND_URL_URL, { cache: "no-cache" })
      .then(function (resp) {
        if (!isContentType(resp, "application/json")) {
          throw new Error("companion plugin not available");
        }
        return resp.json();
      })
      .then(function (data) {
        applyBackground(data && data.url);
      })
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
  }

  try {
    requestGlass();
    requestBackground();
  } catch (e) {
    /* 保持插件原样 */
  }
})();