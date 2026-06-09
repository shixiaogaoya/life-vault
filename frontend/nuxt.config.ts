export default defineNuxtConfig({
  ssr: false,
  compatibilityDate: '2026-06-09',
  modules: ['@nuxtjs/tailwindcss'],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000'
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
