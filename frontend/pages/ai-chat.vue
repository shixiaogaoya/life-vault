<script setup lang="ts">
import type { AIStatus, ChatMessageItem } from '~/types/message'

const {
  getAIStatus,
  aiChat,
  aiSummary,
  aiIndexStart,
  getAIIndexStatus,
} = useApi()

const status = ref<AIStatus | null>(null)
const loadingStatus = ref(false)
const chatMessages = ref<ChatMessageItem[]>([])
const userInput = ref('')
const sending = ref(false)
const chatScope = ref<string>('')  // 空 = 全部
const summaryResult = ref<string>('')
const summaryLoading = ref(false)
const summaryPeriod = ref<'day' | 'week' | 'month'>('week')
const errorMsg = ref('')
const indexPolling = ref<ReturnType<typeof setInterval> | null>(null)

const loadStatus = async () => {
  loadingStatus.value = true
  try {
    status.value = await getAIStatus()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载 AI 状态失败'
  } finally {
    loadingStatus.value = false
  }
}

const sendMessage = async () => {
  const query = userInput.value.trim()
  if (!query || sending.value) return

  if (status.value && !status.value.llm_enabled) {
    errorMsg.value = 'AI 模块未启用。请配置 LIFEVAULT_LLM_PROVIDER 和 LIFEVAULT_LLM_MODEL 环境变量后重启后端。'
    return
  }

  errorMsg.value = ''
  chatMessages.value.push({ role: 'user', content: query })
  userInput.value = ''
  sending.value = true

  try {
    const history = chatMessages.value
      .slice(0, -1)  // 不包含刚加的 user message
      .slice(-6)  // 只保留最近 3 轮对话
      .map(m => ({ role: m.role, content: m.content }))

    const response = await aiChat({
      query,
      chat_id: chatScope.value || undefined,
      history,
    })

    chatMessages.value.push({
      role: 'assistant',
      content: response.answer,
      citations: response.citations,
    })
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : 'AI 聊天失败'
    chatMessages.value.push({
      role: 'assistant',
      content: `_请求失败: ${errorMsg.value}_`,
    })
  } finally {
    sending.value = false
  }
}

const handleEnter = (e: KeyboardEvent) => {
  if (e.shiftKey) return  // Shift+Enter 换行
  e.preventDefault()
  sendMessage()
}

const generateSummary = async () => {
  if (summaryLoading.value) return

  if (status.value && !status.value.llm_enabled) {
    errorMsg.value = 'AI 模块未启用，无法生成摘要。'
    return
  }

  errorMsg.value = ''
  summaryLoading.value = true
  summaryResult.value = ''

  try {
    const response = await aiSummary({
      period: summaryPeriod.value,
      chat_id: chatScope.value || undefined,
    })
    summaryResult.value = response.summary
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '摘要生成失败'
  } finally {
    summaryLoading.value = false
  }
}

const startIndexing = async () => {
  if (status.value && !status.value.embedding_enabled) {
    errorMsg.value = 'Embedding 模块未启用，无法构建索引。'
    return
  }

  errorMsg.value = ''
  try {
    const result = await aiIndexStart()
    if (!result.started) {
      errorMsg.value = result.message
      return
    }
    startIndexPolling()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '启动索引失败'
  }
}

const startIndexPolling = () => {
  if (indexPolling.value) return
  indexPolling.value = setInterval(async () => {
    try {
      const progress = await getAIIndexStatus()
      if (status.value) {
        status.value.index_progress = progress
      }
      if (progress.status === 'completed' || progress.status === 'failed') {
        if (indexPolling.value) {
          clearInterval(indexPolling.value)
          indexPolling.value = null
        }
      }
    } catch (e) {
      // 静默忽略轮询错误
    }
  }, 2000)
}

const formatTimestamp = (ts: number) => {
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

const periodLabels: Record<string, string> = {
  day: '今日',
  week: '本周',
  month: '本月',
}

onMounted(async () => {
  await loadStatus()
  // 如果状态显示索引正在运行，自动开启轮询
  if (status.value?.index_progress.status === 'running') {
    startIndexPolling()
  }
})

onUnmounted(() => {
  if (indexPolling.value) {
    clearInterval(indexPolling.value)
  }
})
</script>

<template>
  <div class="ai-chat-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-6xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">AI 智能助手</h1>
        <p class="text-gray-500 text-sm">基于聊天记录的 RAG 问答与智能摘要</p>
      </header>

      <div v-if="errorMsg" class="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-4">
        {{ errorMsg }}
      </div>

      <section v-if="status" class="bg-white rounded-lg shadow p-4 mb-6">
        <div class="flex items-center justify-between flex-wrap gap-3">
          <div class="flex items-center gap-3">
            <div
              class="w-3 h-3 rounded-full"
              :class="status.llm_enabled ? 'bg-green-500' : 'bg-gray-300'"
            ></div>
            <div>
              <div class="text-sm font-semibold text-gray-900">
                AI {{ status.llm_enabled ? '已启用' : '未启用' }}
              </div>
              <div class="text-xs text-gray-500">
                LLM: {{ status.llm_provider }} / {{ status.llm_model || '-' }}
              </div>
              <div v-if="status.embedding_enabled" class="text-xs text-gray-500">
                Embedding: {{ status.embedding_provider }} / {{ status.embedding_model }}
              </div>
            </div>
          </div>
          <div v-if="status.llm_enabled && status.llm_data_flows_remote"
               class="bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-2 rounded">
            数据将发送至云端 LLM ({{ status.llm_provider }})
          </div>
          <div v-else-if="status.is_local_only && status.llm_enabled"
               class="bg-green-50 border border-green-200 text-green-800 text-xs px-3 py-2 rounded">
            隐私模式：所有数据保留本地
          </div>
        </div>

        <div v-if="!status.llm_enabled" class="mt-3 text-xs text-gray-500 bg-gray-50 p-3 rounded">
          <strong>启用方法：</strong>在后端配置以下环境变量后重启服务：
          <pre class="mt-2 bg-gray-100 p-2 rounded text-xs overflow-x-auto">LIFEVAULT_LLM_PROVIDER=ollama  # 或 openai/anthropic
LIFEVAULT_LLM_MODEL=llama3.2  # 或 gpt-4o-mini / claude-sonnet-4-6
LIFEVAULT_LLM_API_KEY=...     # OpenAI/Anthropic 必填，Ollama 不需要
LIFEVAULT_EMBEDDING_PROVIDER=ollama
LIFEVAULT_EMBEDDING_MODEL=nomic-embed-text</pre>
        </div>
      </section>

      <div v-if="status?.llm_enabled" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section class="lg:col-span-2 bg-white rounded-lg shadow flex flex-col" style="min-height: 600px;">
          <div class="border-b p-4">
            <h2 class="text-lg font-semibold text-gray-900">智能问答</h2>
            <p class="text-xs text-gray-500 mt-1">基于聊天记录的 RAG 检索增强问答</p>
          </div>

          <div class="flex-1 overflow-y-auto p-4 space-y-4" style="max-height: 500px;">
            <div v-if="chatMessages.length === 0" class="text-center text-gray-400 py-12">
              <p>尝试问问：</p>
              <ul class="mt-3 text-sm space-y-1">
                <li>"最近大家在聊什么话题？"</li>
                <li>"有没有讨论过 Python？"</li>
                <li>"找出和某个朋友的所有相关对话"</li>
              </ul>
            </div>

            <div
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              class="flex"
              :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] rounded-lg p-3"
                :class="msg.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-900'"
              >
                <div class="whitespace-pre-wrap">{{ msg.content }}</div>

                <div v-if="msg.citations && msg.citations.length > 0" class="mt-3 pt-3 border-t border-gray-200">
                  <div class="text-xs font-semibold mb-1 opacity-70">引用来源：</div>
                  <ul class="space-y-1">
                    <li
                      v-for="(cite, cIdx) in msg.citations"
                      :key="cIdx"
                      class="text-xs bg-white bg-opacity-50 rounded p-2"
                      :class="msg.role === 'user' ? 'text-blue-50' : 'text-gray-700'"
                    >
                      <div class="font-medium">
                        {{ cite.sender_name || '未知' }} @ {{ cite.chat_name || cite.chat_id }}
                        · {{ formatTimestamp(cite.timestamp) }}
                      </div>
                      <div class="opacity-80 truncate">{{ cite.chunk_text }}</div>
                      <div class="opacity-50">相关度: {{ (cite.score * 100).toFixed(1) }}%</div>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            <div v-if="sending" class="flex justify-start">
              <div class="bg-gray-100 rounded-lg p-3 text-gray-500 text-sm">
                AI 思考中...
              </div>
            </div>
          </div>

          <div class="border-t p-4">
            <div class="flex gap-2 items-end">
              <textarea
                v-model="userInput"
                @keydown.enter="handleEnter"
                :disabled="sending"
                rows="1"
                placeholder="输入问题（Enter 发送，Shift+Enter 换行）..."
                class="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                style="min-height: 40px; max-height: 120px;"
              ></textarea>
              <button
                @click="sendMessage"
                :disabled="sending || !userInput.trim()"
                class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
              >
                发送
              </button>
            </div>
          </div>
        </section>

        <div class="space-y-6">
          <section class="bg-white rounded-lg shadow p-4">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">智能摘要</h2>

            <div class="space-y-3">
              <div>
                <label class="text-xs text-gray-500 block mb-1">时间范围</label>
                <select
                  v-model="summaryPeriod"
                  class="w-full border rounded px-2 py-1 text-sm"
                >
                  <option value="day">今日</option>
                  <option value="week">本周</option>
                  <option value="month">本月</option>
                </select>
              </div>

              <button
                @click="generateSummary"
                :disabled="summaryLoading"
                class="w-full bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
              >
                {{ summaryLoading ? '生成中...' : `生成${periodLabels[summaryPeriod]}摘要` }}
              </button>

              <div v-if="summaryResult" class="mt-3 bg-gray-50 p-3 rounded text-sm text-gray-700 whitespace-pre-wrap max-h-96 overflow-y-auto">
                {{ summaryResult }}
              </div>
            </div>
          </section>

          <section v-if="status?.embedding_enabled" class="bg-white rounded-lg shadow p-4">
            <h2 class="text-lg font-semibold text-gray-900 mb-3">向量索引</h2>

            <div class="text-xs text-gray-500 mb-2">
              索引状态：{{ status.index_progress.status }}
            </div>

            <div v-if="status.index_progress.status === 'running' || status.index_progress.status === 'completed'"
                 class="mb-3">
              <div class="bg-gray-100 rounded h-2 overflow-hidden">
                <div
                  class="bg-blue-500 h-full transition-all"
                  :style="{
                    width: status.index_progress.total > 0
                      ? `${(status.index_progress.processed / status.index_progress.total * 100).toFixed(1)}%`
                      : '0%'
                  }"
                ></div>
              </div>
              <div class="text-xs text-gray-500 mt-1">
                {{ status.index_progress.processed }} / {{ status.index_progress.total }}
                <span v-if="status.index_progress.failed > 0" class="text-red-500">
                  ({{ status.index_progress.failed }} 失败)
                </span>
              </div>
            </div>

            <div v-if="status.index_progress.error" class="text-xs text-red-500 mb-2">
              {{ status.index_progress.error }}
            </div>

            <button
              @click="startIndexing"
              :disabled="status.index_progress.status === 'running'"
              class="w-full bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
            >
              {{ status.index_progress.status === 'running' ? '索引中...' : '构建/更新索引' }}
            </button>

            <p class="text-xs text-gray-400 mt-2">
              索引构建后才能进行 RAG 问答。首次构建可能需要较长时间。
            </p>
          </section>
        </div>
      </div>

      <div v-else-if="!loadingStatus" class="bg-white rounded-lg shadow p-8 text-center">
        <div class="text-4xl mb-3">🔒</div>
        <h2 class="text-xl font-semibold text-gray-900 mb-2">AI 模块未启用</h2>
        <p class="text-gray-500 text-sm mb-4">
          LifeVault 的 AI 功能默认禁用以保护隐私。请配置环境变量后启用。
        </p>
        <div class="bg-gray-50 rounded p-4 text-left text-xs text-gray-700 inline-block">
          <pre># 推荐：本地 Ollama（隐私优先）
LIFEVAULT_LLM_PROVIDER=ollama
LIFEVAULT_LLM_MODEL=llama3.2
LIFEVAULT_EMBEDDING_PROVIDER=ollama
LIFEVAULT_EMBEDDING_MODEL=nomic-embed-text

# 或：OpenAI 云端
LIFEVAULT_LLM_PROVIDER=openai
LIFEVAULT_LLM_MODEL=gpt-4o-mini
LIFEVAULT_LLM_API_KEY=sk-...</pre>
        </div>
      </div>
    </div>
  </div>
</template>
