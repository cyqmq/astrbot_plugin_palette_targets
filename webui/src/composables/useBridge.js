/**
 * AstrBot Plugin Page Bridge API 封装（Vuetify 模板）。
 *
 * 参考 astrbot_plugin_angel_memory 的 useBridge.ts：
 * - 生产环境：AstrBot 加载插件页面时自动注入 bridge-sdk.js，
 *   使用 window.AstrBotPluginPage 与后端通信；
 * - 开发环境（vite dev）：无 bridge 时回退到本地 HTTP 代理，便于独立调试。
 */

function getBridge() {
  if (typeof window !== 'undefined' && window.AstrBotPluginPage) {
    return window.AstrBotPluginPage
  }
  return null
}

// postMessage 结构化克隆不接受 Vue 的 Proxy，过桥前先落为纯 JSON
function plain(value) {
  return value === undefined ? value : JSON.parse(JSON.stringify(value))
}

export function useBridge() {
  const bridge = getBridge()

  async function init() {
    if (!bridge) {
      console.warn('[Bridge] AstrBotPluginPage 不可用，可能在独立开发模式下运行')
      return null
    }
    try {
      return await bridge.ready()
    } catch (e) {
      console.error('[Bridge] 初始化失败:', e)
      return null
    }
  }

  async function apiGet(endpoint, params) {
    if (bridge) {
      return await bridge.apiGet(endpoint, plain(params))
    }
    // 开发模式回退：直接请求本地后端
    const url = new URL(`/api/plug/astrbot_plugin_palette_targets/${endpoint}`, window.location.origin)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
      })
    }
    const resp = await fetch(url.toString())
    return resp.json()
  }

  async function apiPost(endpoint, body) {
    if (bridge) {
      return await bridge.apiPost(endpoint, plain(body))
    }
    const url = `/api/plug/astrbot_plugin_palette_targets/${endpoint}`
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return resp.json()
  }

  return { init, apiGet, apiPost }
}