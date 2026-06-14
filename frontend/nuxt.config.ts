export default defineNuxtConfig({
  ssr: false,
  compatibilityDate: '2026-06-09',
  modules: ['@nuxtjs/tailwindcss'],
  runtimeConfig: {
    public: {
      // 默认空串 = 同源（Docker / 反向代理部署时由 nginx 转发 /api/* 到后端）。
      // 本地开发前后端分离时，设置 NUXT_PUBLIC_API_BASE=http://localhost:8000。
      apiBase: process.env.NUXT_PUBLIC_API_BASE || ''
    }
  },
  nitro: {
    static: true
  },
  app: {
    head: {
      title: 'LifeVault - 个人消息档案',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' }
      ]
    }
  }
})
