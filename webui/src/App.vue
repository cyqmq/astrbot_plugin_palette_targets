<template>
  <v-app>
    <v-main>
      <v-container fluid class="pa-4">
        <v-card class="mb-4" elevation="0">
          <v-card-title class="text-h6">Vuetify 3 插件视图模板</v-card-title>
          <v-card-text>
            这是一个基于 Vite + Vue 3 + Vuetify 3 的插件视图示例。
            <br />
            主题通过 Bridge SDK 维护的 <code>data-theme</code> 属性与 AstrBot
            仪表盘实时同步。
          </v-card-text>
        </v-card>

        <v-card elevation="0">
          <v-card-title class="text-subtitle-1">表单示例</v-card-title>
          <v-card-text>
            <v-text-field
              label="测试输入框"
              variant="outlined"
              density="comfortable"
              class="mb-4"
            />
            <v-select
              label="测试下拉框"
              :items="['选项一', '选项二', '选项三']"
              variant="outlined"
              density="comfortable"
              class="mb-4"
            />
            <v-btn color="primary" variant="elevated" @click="onCallBridge">
              调用 Bridge 后端 API
            </v-btn>
            <div v-if="apiResult" class="mt-4 text-body-2">
              返回：{{ apiResult }}
            </div>
          </v-card-text>
        </v-card>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useTheme } from 'vuetify'
import { useBridge } from './composables/useBridge'

const theme = useTheme()
const bridge = useBridge()
const apiResult = ref('')

let observer = null

function syncTheme() {
  // 官方机制：Bridge SDK 在 <html> 上维护 data-theme 属性
  const dataTheme = document.documentElement.getAttribute('data-theme')
  theme.global.name.value = dataTheme === 'light' ? 'light' : 'dark'
}

onMounted(() => {
  observer = new MutationObserver(syncTheme)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
  syncTheme()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})

async function onCallBridge() {
  try {
    const data = await bridge.apiGet('background-info')
    apiResult.value = JSON.stringify(data)
  } catch (e) {
    apiResult.value = `调用失败：${e?.message || e}`
  }
}
</script>

<style>
/* 保持 AstrBot 原版卡片观感：实色表面 + 1px 边框 */
.v-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12) !important;
}
</style>