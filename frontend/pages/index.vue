<script setup lang="ts">
import type { MessageListItem } from '~/types/message'

const { getMessages, getStats } = useApi()

const stats = ref<any>(null)
const messages = ref<MessageListItem[]>([])
const page = ref(1)
const loading = ref(false)
const hasMore = ref(true)
const total = ref(0)

const filters = ref({
  chat_id: '',
  date_from: '',
  date_to: '',
})

const loadMessages = async (reset = false) => {
  if (loading.value || (!hasMore.value && !reset)) return

  loading.value = true
  try {
    if (reset) {
      page.value = 1
      messages.value = []
      hasMore.value = true
    }

    const response = await getMessages({
      page: page.value,
      page_size: 50,
      ...filters.value,
    })

    if (reset) {
      messages.value = response.messages
    } else {
      messages.value.push(...response.messages)
    }

    total.value = response.total
    hasMore.value = messages.value.length < response.total
    page.value++
  } catch (error) {
    console.error('Failed to load messages:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    stats.value = await getStats()
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const handleFilterChange = (newFilters: any) => {
  filters.value = newFilters
  loadMessages(true)
}

const observerTarget = ref<HTMLElement | null>(null)

onMounted(() => {
  loadStats()
  loadMessages()

  if (observerTarget.value) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading.value && hasMore.value) {
          loadMessages()
        }
      },
      { threshold: 0.1 }
    )
    observer.observe(observerTarget.value)
  }
})
</script>

<template>
  <div class="home-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-4xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-4">LifeVault - 个人消息档案</h1>

        <div v-if="stats" class="stats-overview grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-sm text-gray-500">总消息数</div>
            <div class="text-2xl font-bold text-blue-600">{{ stats.total_messages.toLocaleString() }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-sm text-gray-500">聊天对象</div>
            <div class="text-2xl font-bold text-green-600">{{ stats.chat_count }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-sm text-gray-500">数据源</div>
            <div class="text-2xl font-bold text-purple-600">{{ Object.keys(stats.sources).length }}</div>
          </div>
        </div>
      </header>

      <FilterBar @filter-change="handleFilterChange" />

      <div class="message-timeline">
        <MessageCard
          v-for="message in messages"
          :key="message.id"
          :message="message"
        />

        <div v-if="loading" class="text-center py-4">
          <span class="text-gray-500">加载中...</span>
        </div>

        <div v-if="!loading && !hasMore && messages.length > 0" class="text-center py-4">
          <span class="text-gray-400">没有更多消息了</span>
        </div>

        <div v-if="!loading && messages.length === 0" class="text-center py-8">
          <span class="text-gray-400">暂无消息</span>
        </div>

        <div ref="observerTarget" class="h-4"></div>
      </div>
    </div>
  </div>
</template>
