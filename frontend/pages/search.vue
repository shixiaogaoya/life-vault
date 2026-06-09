<script setup lang="ts">
import type { UnifiedMessage } from '~/types/message'

const { searchMessages } = useApi()

const query = ref('')
const results = ref<UnifiedMessage[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)

const search = async () => {
  if (!query.value.trim()) return

  loading.value = true
  try {
    const response = await searchMessages({
      q: query.value,
      page: page.value,
      page_size: 50,
    })

    results.value = response.results
    total.value = response.total
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    loading.value = false
  }
}

const highlightKeyword = (content: string, keyword: string): string => {
  if (!keyword) return content
  const regex = new RegExp(`(${keyword})`, 'gi')
  return content.replace(regex, '<mark class="bg-yellow-200">$1</mark>')
}

const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}
</script>

<template>
  <div class="search-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-4xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-4">消息搜索</h1>
      </header>

      <div class="search-box mb-6">
        <div class="flex gap-2">
          <input
            v-model="query"
            type="text"
            placeholder="输入关键词搜索..."
            class="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            @keyup.enter="search"
          >
          <button
            class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            @click="search"
          >
            搜索
          </button>
        </div>
        <div v-if="total > 0" class="text-sm text-gray-500 mt-2">
          找到 {{ total }} 条结果
        </div>
      </div>

      <div class="search-results">
        <div
          v-for="result in results"
          :key="result.id"
          class="result-item bg-white rounded-lg shadow p-4 mb-3 hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium text-gray-900">{{ result.sender_name || result.chat_name }}</span>
            <span class="text-xs text-gray-500">{{ formatTime(result.timestamp) }}</span>
          </div>
          <div class="text-sm text-gray-600 mb-2">
            <span class="text-xs text-gray-400">{{ result.type_name }}</span>
          </div>
          <div
            class="snippet text-sm text-gray-800"
            v-html="highlightKeyword(result.content, query)"
          ></div>
        </div>

        <div v-if="loading" class="text-center py-8">
          <span class="text-gray-500">搜索中...</span>
        </div>

        <div v-if="!loading && results.length === 0 && query" class="text-center py-8">
          <span class="text-gray-400">没有找到相关消息</span>
        </div>
      </div>
    </div>
  </div>
</template>
