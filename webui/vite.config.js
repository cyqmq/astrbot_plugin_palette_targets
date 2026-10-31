import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { fileURLToPath, URL } from 'url'

export default defineConfig({
  plugins: [vue()],
  // 相对路径，避免 iframe 内资源路径错误
  base: './',
  build: {
    // 构建产物输出到插件 pages/<页面名>/，AstrBot 自动发现为插件视图
    outDir: resolve(__dirname, '../pages/vuetify-demo'),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        // 全部打成单文件，避免 iframe CORS 问题
        inlineDynamicImports: true,
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})