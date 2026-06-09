<script setup lang="ts">
import type { UnifiedMessage } from '~/types/message'

interface Props {
  message: UnifiedMessage
}

const props = defineProps<Props>()

const typeIcons: Record<number, string> = {
  1: '💬',
  3: '🖼️',
  34: '🎤',
  43: '🎬',
  49: '📎',
  47: '😊',
  48: '📍',
  50: '📞',
  10000: '📢',
}

const formatTime = (timestamp: number): string => {
  const now = Date.now() / 1000
  const diff = now - timestamp

  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 172800) return '昨天'

  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString('zh-CN')
}

const truncateContent = (content: string, maxLength = 100): string => {
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength) + '...'
}
</script>

<template>
  <div class="message-card bg-white rounded-lg shadow p-4 mb-3 hover:shadow-md transition-shadow">
    <div class="flex items-start gap-3">
      <div class="text-2xl flex-shrink-0">
        {{ typeIcons[message.msg_type] || '📄' }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center justify-between mb-1">
          <span class="font-medium text-gray-900">{{ message.sender_name || message.chat_name }}</span>
          <span class="text-xs text-gray-500">{{ formatTime(message.timestamp) }}</span>
        </div>
        <div class="text-sm text-gray-600 mb-1">
          <span class="text-xs text-gray-400">{{ message.type_name }}</span>
        </div>
        <p class="text-sm text-gray-800 break-words">
          {{ truncateContent(message.content) }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-card {
  cursor: pointer;
}
</style>
