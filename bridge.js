/*
 * astrbot_plugin_palette_targets 主文档桥接脚本。
 *
 * 由本插件幂等注入到 AstrBot dashboard 的 data/dist/index.html。
 * 作用：监听调色盘主插件（astrbot_plugin_palette）在同源多标签页间
 * 广播的配置变化事件（BroadcastChannel + localStorage storage 脉冲），
 * 并转发给页面内的插件视图 iframe（如 MonkeyCode 设置页），
 * 使 minimal_adapter.js 无需轮询即可实时刷新毛玻璃背景/主题。
 *
 * 若主插件未安装或未广播，本脚本不产生任何影响。
 */
(function () {
  "use strict";

  var SYNC_CHANNEL = "astrbot-palette-sync";
  var SYNC_EVENT_KEY = "astrbot_palette_sync_event";
  var MSG_CHANNEL = "astrbot-palette-targets";
  var bc = null;

  function notifyFrames() {
    for (var i = 0; i < window.frames.length; i++) {
      try {
        window.frames[i].postMessage(
          { channel: MSG_CHANNEL, kind: "refresh" },
          "*"
        );
      } catch (e) {
        /* 忽略不可访问的 frame */
      }
    }
  }

  try {
    if (typeof BroadcastChannel === "function") {
      bc = new BroadcastChannel(SYNC_CHANNEL);
      bc.onmessage = function (event) {
        if (event && event.data && event.data.id) {
          notifyFrames();
        }
      };
    }
  } catch (e) {
    bc = null;
  }

  window.addEventListener("storage", function (event) {
    if (event && event.key === SYNC_EVENT_KEY && event.newValue) {
      notifyFrames();
    }
  });
})();