<script setup lang="ts">
import type { AIStatus, ChatMessageItem } from '~/types/message'

const {
  getAIStatus,
  getAIConfig,
  saveAIConfig,
  testAIConnection,
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

// ===== AI 配置面板（运行时填写，无需环境变量或重启） =====
const showConfig = ref(false)
const configSaving = ref(false)
const configForm = reactive({
  llm_provider: 'openai',
  llm_model: '',
  llm_api_key: '',
  llm_base_url: '',
  embedding_provider: 'openai',
  embedding_model: '',
  embedding_api_key: '',
  embedding_base_url: '',
})
// 标记 api_key 是否已配置（从后端读取，决定是否显示「已设置」提示）
const llmApiKeySet = ref(false)
const embeddingApiKeySet = ref(false)

const providerOptions = [
  { value: 'openai', label: 'OpenAI 兼容（DeepSeek / OpenAI / Moonshot 等）' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'ollama', label: 'Ollama（本地，隐私优先）' },
]
const embeddingProviderOptions = [
  { value: 'openai', label: 'OpenAI 兼容 Embeddings' },
  { value: 'ollama', label: 'Ollama Embeddings（本地）' },
]

/**
 * 服务商预设：点击后自动填入 base_url + 推荐模型名，用户只需补 API Key。
 * 所有预设都走 OpenAI 兼容协议（llm_provider=openai），
 * 因为 DeepSeek / Moonshot / 智谱等都兼容 OpenAI API 格式。
 */
interface Preset {
  key: string
  label: string
  llm_base_url: string
  llm_model: string
  // embedding 配置（部分服务商不提供 embedding API，用 null 表示需另配）
  embedding_base_url?: string
  embedding_model?: string
  needs_api_key: boolean
  help_url?: string
}

const llmPresets: Preset[] = [
  {
    key: 'deepseek',
    label: 'DeepSeek（推荐，性价比高）',
    llm_base_url: 'https://api.deepseek.com/v1',
    llm_model: 'deepseek-chat',
    needs_api_key: true,
    help_url: 'https://platform.deepseek.com/api_keys',
  },
  {
    key: 'openai',
    label: 'OpenAI 官方',
    llm_base_url: 'https://api.openai.com/v1',
    llm_model: 'gpt-4o-mini',
    embedding_base_url: 'https://api.openai.com/v1',
    embedding_model: 'text-embedding-3-small',
    needs_api_key: true,
    help_url: 'https://platform.openai.com/api-keys',
  },
  {
    key: 'moonshot',
    label: 'Moonshot（Kimi）',
    llm_base_url: 'https://api.moonshot.cn/v1',
    llm_model: 'moonshot-v1-8k',
    embedding_base_url: 'https://api.moonshot.cn/v1',
    embedding_model: 'text-embedding-1',
    needs_api_key: true,
    help_url: 'https://platform.moonshot.cn/console/api-keys',
  },
  {
    key: 'ollama',
    label: 'Ollama（本地，隐私优先，免费）',
    llm_base_url: 'http://localhost:11434/v1',
    llm_model: 'llama3.2',
    embedding_base_url: 'http://localhost:11434/v1',
    embedding_model: 'nomic-embed-text',
    needs_api_key: false,
    help_url: 'https://ollama.com/download',
  },
]

const embeddingPresets: Preset[] = [
  {
    key: 'openai-emb',
    label: 'OpenAI Embeddings（需 OpenAI Key）',
    llm_base_url: '',
    llm_model: '',
    embedding_base_url: 'https://api.openai.com/v1',
    embedding_model: 'text-embedding-3-small',
    needs_api_key: true,
  },
  {
    key: 'ollama-emb',
    label: 'Ollama Embeddings（本地，免费）',
    llm_base_url: '',
    llm_model: '',
    embedding_base_url: 'http://localhost:11434/v1',
    embedding_model: 'nomic-embed-text',
    needs_api_key: false,
  },
  {
    key: 'deepseek-emb',
    label: 'DeepSeek（暂不提供 Embedding API，请选其他）',
    llm_base_url: '',
    llm_model: '',
    embedding_base_url: '',
    embedding_model: '',
    needs_api_key: false,
  },
]

/** 应用 LLM 预设：自动填入 base_url + model，切换 provider */
const applyLlmPreset = (preset: Preset) => {
  // Ollama 预设切换 provider 为 ollama（后端走不同的 provider 逻辑）
  configForm.llm_provider = preset.key === 'ollama' ? 'ollama' : 'openai'
  configForm.llm_base_url = preset.llm_base_url
  configForm.llm_model = preset.llm_model
  // 如果预设包含 embedding 配置，一并填入
  if (preset.embedding_base_url) {
    configForm.embedding_provider = preset.key === 'ollama' ? 'ollama' : 'openai'
    configForm.embedding_base_url = preset.embedding_base_url
    configForm.embedding_model = preset.embedding_model || ''
  }
}

/** 应用 Embedding 预设 */
const applyEmbeddingPreset = (preset: Preset) => {
  if (!preset.embedding_base_url) return  // DeepSeek 那条不可选
  configForm.embedding_provider = preset.key === 'ollama-emb' ? 'ollama' : 'openai'
  configForm.embedding_base_url = preset.embedding_base_url
  configForm.embedding_model = preset.embedding_model || ''
}

const loadConfig = async () => {
  try {
    const cfg = await getAIConfig() as Record<string, any>
    configForm.llm_provider = cfg.llm_provider || 'openai'
    configForm.llm_model = cfg.llm_model || ''
    configForm.llm_base_url = cfg.llm_base_url || ''
    configForm.embedding_provider = cfg.embedding_provider || 'openai'
    configForm.embedding_model = cfg.embedding_model || ''
    configForm.embedding_base_url = cfg.embedding_base_url || ''
    llmApiKeySet.value = !!cfg.llm_api_key_set
    embeddingApiKeySet.value = !!cfg.embedding_api_key_set
    // api_key 不回填（安全考虑），留空让用户重新输入或保持不变
    configForm.llm_api_key = ''
    configForm.embedding_api_key = ''
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载配置失败'
  }
}

const saveConfig = async () => {
  configSaving.value = true
  errorMsg.value = ''
  try {
    // 只提交非空字段；api_key 为空时不提交（保留原值）
    const update: Record<string, string> = {}
    for (const [k, v] of Object.entries(configForm)) {
      if (v !== '' && v !== null && v !== undefined) update[k] = v
    }
    await saveAIConfig(update)
    await loadStatus()  // 刷新状态（llm_enabled 应变为 true）
    showConfig.value = false
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '保存配置失败'
  } finally {
    configSaving.value = false
  }
}

// ===== 模型拉取与连接测试 =====
const llmModels = ref<string[]>([])         // 拉取到的 LLM 模型列表
const embeddingModels = ref<string[]>([])   // 拉取到的 embedding 模型列表
const fetchingModels = ref(false)           // 拉取中
const testingConnection = ref(false)        // 测试连接中
const testResult = ref<{ ok: boolean; msg: string } | null>(null)

/**
 * 获取用于测试的 API Key：
 * 用户在表单里新填的 llm_api_key 优先；没填则用空串
 * （后端会用已保存的 key 测试，但 /test 端点是独立的，需要显式传 key）。
 * 如果用户没输入新 key 且已有保存的 key，提示用户先输入。
 */
const resolveTestApiKey = (field: 'llm' | 'embedding'): string => {
  const newKey = field === 'llm' ? configForm.llm_api_key : configForm.embedding_api_key
  if (newKey) return newKey
  // 没输入新 key：Ollama 不需要 key，直接返回空
  const provider = field === 'llm' ? configForm.llm_provider : configForm.embedding_provider
  if (provider === 'ollama') return ''
  return ''  // 云端 provider 没填 key 时后端会返回错误，由 UI 引导
}

/** 拉取 LLM 模型列表（调后端 /api/ai/test，kind=llm） */
const fetchLlmModels = async () => {
  if (!configForm.llm_base_url) {
    errorMsg.value = '请先填写 API Base URL 或选择服务商预设'
    return
  }
  fetchingModels.value = true
  errorMsg.value = ''
  try {
    const result = await testAIConnection({
      base_url: configForm.llm_base_url,
      api_key: resolveTestApiKey('llm'),
      provider: configForm.llm_provider as 'openai' | 'ollama',
      kind: 'llm',
    })
    if (result.ok && result.models.length > 0) {
      llmModels.value = result.models
      // 如果当前模型不在列表里，默认选第一个
      if (!configForm.llm_model || !result.models.includes(configForm.llm_model)) {
        configForm.llm_model = result.models[0]
      }
      testResult.value = { ok: true, msg: `拉取到 ${result.models.length} 个模型（${result.latency_ms}ms）` }
    } else {
      testResult.value = { ok: false, msg: result.error || '未找到可用模型' }
    }
  } catch (e) {
    testResult.value = { ok: false, msg: e instanceof Error ? e.message : '拉取失败' }
  } finally {
    fetchingModels.value = false
  }
}

/** 拉取 Embedding 模型列表（kind=embedding） */
const fetchEmbeddingModels = async () => {
  if (!configForm.embedding_base_url) {
    errorMsg.value = '请先填写 Embedding API Base URL 或选择预设'
    return
  }
  fetchingModels.value = true
  errorMsg.value = ''
  try {
    const result = await testAIConnection({
      base_url: configForm.embedding_base_url,
      api_key: resolveTestApiKey('embedding'),
      provider: configForm.embedding_provider as 'openai' | 'ollama',
      kind: 'embedding',
    })
    if (result.ok && result.models.length > 0) {
      embeddingModels.value = result.models
      if (!configForm.embedding_model || !result.models.includes(configForm.embedding_model)) {
        configForm.embedding_model = result.models[0]
      }
      testResult.value = { ok: true, msg: `Embedding：拉取到 ${result.models.length} 个模型` }
    } else {
      testResult.value = { ok: false, msg: result.error || '未找到 embedding 模型' }
    }
  } catch (e) {
    testResult.value = { ok: false, msg: e instanceof Error ? e.message : '拉取失败' }
  } finally {
    fetchingModels.value = false
  }
}

/**
 * 测试当前表单配置的完整连通性：
 * 同时测试 LLM 和 Embedding，确认两者都能正常请求。
 */
const testConnection = async () => {
  testingConnection.value = true
  testResult.value = null
  errorMsg.value = ''
  try {
    const results: string[] = []

    // 测 LLM
    if (configForm.llm_base_url) {
      const r = await testAIConnection({
        base_url: configForm.llm_base_url,
        api_key: resolveTestApiKey('llm'),
        provider: configForm.llm_provider as 'openai' | 'ollama',
        kind: 'llm',
      })
      if (r.ok) {
        results.push(`LLM ✓ (${r.latency_ms}ms, ${r.models.length} 模型)`)
        if (r.models.length > 0 && !r.models.includes(configForm.llm_model)) {
          configForm.llm_model = r.models[0]
        }
        llmModels.value = r.models
      } else {
        results.push(`LLM ✗ ${r.error}`)
      }
    }

    // 测 Embedding
    if (configForm.embedding_base_url) {
      const r = await testAIConnection({
        base_url: configForm.embedding_base_url,
        api_key: resolveTestApiKey('embedding'),
        provider: configForm.embedding_provider as 'openai' | 'ollama',
        kind: 'embedding',
      })
      if (r.ok) {
        results.push(`Embedding ✓ (${r.latency_ms}ms)`)
        embeddingModels.value = r.models
      } else {
        results.push(`Embedding ✗ ${r.error}`)
      }
    }

    const allOk = results.every(r => r.includes('✓'))
    testResult.value = { ok: allOk, msg: results.join('  |  ') }
  } catch (e) {
    testResult.value = { ok: false, msg: e instanceof Error ? e.message : '测试失败' }
  } finally {
    testingConnection.value = false
  }
}

const openConfig = async () => {
  showConfig.value = true
  testResult.value = null
  llmModels.value = []
  embeddingModels.value = []
  await loadConfig()
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
          <div class="flex items-center gap-2">
            <div v-if="status.llm_enabled && status.llm_data_flows_remote"
                 class="bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-2 rounded">
              数据将发送至云端 LLM ({{ status.llm_provider }})
            </div>
            <div v-else-if="status.is_local_only && status.llm_enabled"
                 class="bg-green-50 border border-green-200 text-green-800 text-xs px-3 py-2 rounded">
              隐私模式：所有数据保留本地
            </div>
            <button
              @click="openConfig"
              class="text-sm px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50 text-gray-700"
            >
              ⚙ {{ status.llm_enabled ? '修改配置' : '配置 AI' }}
            </button>
          </div>
        </div>

        <!-- 配置表单（默认折叠，点击「配置 AI」展开） -->
        <div v-if="showConfig" class="mt-4 border-t pt-4 space-y-4">
          <h3 class="text-sm font-semibold text-gray-800">AI 配置</h3>
          <p class="text-xs text-gray-500">
            填写后保存即立即生效，无需重启。API Key 仅保存在本地配置文件，不上传任何服务器。
          </p>

          <!-- LLM 配置 -->
          <div class="bg-gray-50 rounded p-3 space-y-3">
            <div class="text-xs font-semibold text-gray-700 uppercase tracking-wide">LLM（问答与摘要）</div>

            <!-- 服务商快捷预设 -->
            <div>
              <div class="text-xs text-gray-500 mb-1.5">快捷选择服务商（自动填入地址和模型名，只需补 API Key）：</div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="preset in llmPresets"
                  :key="preset.key"
                  @click="applyLlmPreset(preset)"
                  class="text-xs px-2.5 py-1 rounded border border-gray-300 bg-white hover:bg-blue-50 hover:border-blue-300 text-gray-700"
                >
                  {{ preset.label }}
                </button>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label class="block">
                <span class="text-xs text-gray-600">Provider（协议类型）</span>
                <select v-model="configForm.llm_provider" class="mt-1 w-full border rounded px-2 py-1.5 text-sm">
                  <option v-for="opt in providerOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </label>

              <!-- 模型名：支持下拉选择（拉取后）或手动输入 -->
              <label class="block">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-gray-600">模型名</span>
                  <button
                    type="button"
                    @click="fetchLlmModels"
                    :disabled="fetchingModels || !configForm.llm_base_url"
                    class="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {{ fetchingModels ? '拉取中...' : (llmModels.length > 0 ? '↻ 刷新模型' : '↓ 拉取模型') }}
                  </button>
                </div>
                <select
                  v-if="llmModels.length > 0"
                  v-model="configForm.llm_model"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm bg-white"
                >
                  <option v-for="m in llmModels" :key="m" :value="m">{{ m }}</option>
                </select>
                <input
                  v-else
                  v-model="configForm.llm_model"
                  type="text"
                  placeholder="点击「拉取模型」自动获取，或手动输入"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                />
              </label>

              <label class="block">
                <span class="text-xs text-gray-600">API Base URL</span>
                <input v-model="configForm.llm_base_url" type="text" placeholder="https://api.deepseek.com/v1"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm" />
              </label>
              <label class="block">
                <span class="text-xs text-gray-600">
                  API Key
                  <span v-if="llmApiKeySet" class="text-green-600 ml-1">（已设置，留空保持不变）</span>
                </span>
                <input v-model="configForm.llm_api_key" type="password" placeholder="sk-..."
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm" />
              </label>
            </div>
          </div>

          <!-- Embedding 配置 -->
          <div class="bg-gray-50 rounded p-3 space-y-3">
            <div class="text-xs font-semibold text-gray-700 uppercase tracking-wide">Embedding（语义检索，RAG 必需）</div>
            <p class="text-xs text-gray-500">
              ⚠️ DeepSeek 目前不提供 Embedding API。若 LLM 用 DeepSeek，这里请选 OpenAI Embeddings 或 Ollama（本地免费）。
            </p>

            <!-- Embedding 快捷预设 -->
            <div class="flex flex-wrap gap-2">
              <button
                v-for="preset in embeddingPresets"
                :key="preset.key"
                @click="applyEmbeddingPreset(preset)"
                :disabled="!preset.embedding_base_url"
                class="text-xs px-2.5 py-1 rounded border border-gray-300 bg-white hover:bg-blue-50 hover:border-blue-300 text-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {{ preset.label }}
              </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label class="block">
                <span class="text-xs text-gray-600">Provider</span>
                <select v-model="configForm.embedding_provider" class="mt-1 w-full border rounded px-2 py-1.5 text-sm">
                  <option v-for="opt in embeddingProviderOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </label>
              <label class="block">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-gray-600">模型名</span>
                  <button
                    type="button"
                    @click="fetchEmbeddingModels"
                    :disabled="fetchingModels || !configForm.embedding_base_url"
                    class="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {{ fetchingModels ? '拉取中...' : (embeddingModels.length > 0 ? '↻ 刷新模型' : '↓ 拉取模型') }}
                  </button>
                </div>
                <select
                  v-if="embeddingModels.length > 0"
                  v-model="configForm.embedding_model"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm bg-white"
                >
                  <option v-for="m in embeddingModels" :key="m" :value="m">{{ m }}</option>
                </select>
                <input
                  v-else
                  v-model="configForm.embedding_model"
                  type="text"
                  placeholder="点击「拉取模型」自动获取，或手动输入"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm"
                />
              </label>
              <label class="block">
                <span class="text-xs text-gray-600">API Base URL（可选）</span>
                <input v-model="configForm.embedding_base_url" type="text" placeholder="https://api.openai.com/v1"
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm" />
              </label>
              <label class="block">
                <span class="text-xs text-gray-600">
                  API Key
                  <span v-if="embeddingApiKeySet" class="text-green-600 ml-1">（已设置，留空保持不变）</span>
                </span>
                <input v-model="configForm.embedding_api_key" type="password" placeholder="sk-..."
                  class="mt-1 w-full border rounded px-2 py-1.5 text-sm" />
              </label>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button
              @click="saveConfig"
              :disabled="configSaving"
              class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white text-sm px-4 py-2 rounded"
            >
              {{ configSaving ? '保存中...' : '保存并启用' }}
            </button>
            <button
              @click="testConnection"
              :disabled="testingConnection"
              class="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-gray-700 text-sm px-4 py-2 rounded"
            >
              {{ testingConnection ? '测试中...' : '🔌 测试连接' }}
            </button>
            <button @click="showConfig = false" class="text-sm text-gray-500 hover:text-gray-700">取消</button>
          </div>

          <!-- 测试 / 拉取结果 -->
          <div v-if="testResult" class="text-xs p-2 rounded"
            :class="testResult.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'"
          >
            {{ testResult.ok ? '✓' : '✗' }} {{ testResult.msg }}
          </div>
        </div>

        <!-- 未启用提示（配置表单未展开时） -->
        <div v-if="!status.llm_enabled && !showConfig" class="mt-3 text-sm text-gray-600 bg-blue-50 border border-blue-200 p-3 rounded">
          点击右上角「配置 AI」，填写 API Key 和模型名即可启用，无需环境变量或重启。
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
