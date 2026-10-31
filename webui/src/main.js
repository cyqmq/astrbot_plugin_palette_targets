import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

import App from './App.vue'
import { useBridge } from './composables/useBridge'

const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi',
  },
  theme: {
    defaultTheme: 'dark',
    themes: {
      light: {
        dark: false,
        colors: {
          primary: '#3c96ca',
          secondary: '#2f86bd',
          surface: '#ffffff',
          background: '#ffffff',
        },
      },
      dark: {
        dark: true,
        colors: {
          primary: '#5ba4d4',
          secondary: '#4a95c4',
          surface: '#242424',
          background: '#1a1a1a',
        },
      },
    },
  },
})

const app = createApp(App)
app.use(vuetify)
app.mount('#app')

// 初始化 AstrBot Bridge（AstrBot 加载页面时自动注入 bridge-sdk.js）
useBridge().init()