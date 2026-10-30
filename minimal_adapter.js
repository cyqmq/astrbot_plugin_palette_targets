/*
 * minimal_adapter.js — AstrBot 调色盘毛玻璃最小接入器（约 20 行）。
 *
 * 用法：复制本文件到你的插件 <views>/<视图名>/ 目录，然后在 index.html 中引入：
 *   <script src="./minimal_adapter.js"></script>
 *
 * 行为：
 *   - 已安装 astrbot_plugin_palette_targets：自动请求并注入毛玻璃样式，
 *     让你的设置页透出调色盘壁纸（半透明 + backdrop-filter）。
 *   - 未安装该附属插件：请求 404，静默失败，插件保持原本外观，零影响。
 */
(function () {
  "use strict";

  var GLASS_CSS_URL =
    "/api/v1/plugins/extensions/astrbot_plugin_palette_targets/glass.css";
  var STYLE_ID = "astrbot-palette-glass";

  function inject(css) {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = css;
    document.head.appendChild(style);
  }

  try {
    fetch(GLAS_CSS_URL, { cache: "no-cache" })
      .then(function (resp) {
        var type = (resp.headers.get("content-type") || "").toLowerCase();
        if (!resp.ok || type.indexOf("text/css") !== 0) {
          throw new Error("companion plugin not available");
        }
        return resp.text();
      })
      .then(inject)
      .catch(function () {
        /* 无附属插件：保持插件原样 */
      });
  } catch (e) {
    /* 保持插件原样 */
  }
})();