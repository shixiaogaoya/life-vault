import type {
  AIChatResponse,
  AIConfigUpdate,
  AISummaryResponse,
  AIStatus,
  ContactActivityStatsResponse,
  ImportResponse,
  IndexStatus,
  MessageListResponse,
  RelationshipAnalysisResponse,
  SearchResponse,
  StatsResponse,
  TopicClustersResponse,
  VisualizationStatsResponse,
} from '~/types/message'

export const useApi = () => {
  const config = useRuntimeConfig()
  // 同源默认（Docker / 反代部署走 /api/*）
  const defaultBaseURL = config.public.apiBase

  /**
   * 桌面端后端基址缓存。
   *
   * Electron 主进程在启动时为后端分配了随机端口，并通过 preload 注入的
   * window.lifevault.getBackendBaseUrl() 暴露给渲染进程。
   * 这里懒加载一次并缓存，避免每个请求都走一次 IPC。
   *
   * - Web 端：window.lifevault 不存在 → 直接返回 defaultBaseURL
   * - 桌面端：首次调用时通过 IPC 拿到 http://127.0.0.1:<port>，之后复用
   * - 异常容错：桌面端 IPC 失败时回退到 defaultBaseURL，保证基本可用
   */
  let cachedDesktopBaseURL: string | null = null
  const resolveBaseURL = async (): Promise<string> => {
    if (cachedDesktopBaseURL !== null) return cachedDesktopBaseURL
    if (typeof window === 'undefined' || !window.lifevault) {
      cachedDesktopBaseURL = defaultBaseURL
      return defaultBaseURL
    }
    try {
      const url = await window.lifevault.getBackendBaseUrl()
      cachedDesktopBaseURL = url || defaultBaseURL
    } catch {
      cachedDesktopBaseURL = defaultBaseURL
    }
    return cachedDesktopBaseURL
  }

  const getMessages = async (params: {
    page?: number
    page_size?: number
    chat_id?: string
    date_from?: string
    date_to?: string
  } = {}): Promise<MessageListResponse> => {
    const query = new URLSearchParams()
    if (params.page) query.append('page', params.page.toString())
    if (params.page_size) query.append('page_size', params.page_size.toString())
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)

    const response = await fetch(`${await resolveBaseURL()}/api/messages?${query}`)
    if (!response.ok) throw new Error('Failed to fetch messages')
    return response.json()
  }

  const searchMessages = async (params: {
    q: string
    page?: number
    page_size?: number
  }): Promise<SearchResponse> => {
    const query = new URLSearchParams()
    query.append('q', params.q)
    if (params.page) query.append('page', params.page.toString())
    if (params.page_size) query.append('page_size', params.page_size.toString())

    const response = await fetch(`${await resolveBaseURL()}/api/search?${query}`)
    if (!response.ok) throw new Error('Failed to search messages')
    return response.json()
  }

  const getStats = async (): Promise<StatsResponse> => {
    const response = await fetch(`${await resolveBaseURL()}/api/stats`)
    if (!response.ok) throw new Error('Failed to fetch stats')
    return response.json()
  }

  const getVisualizationStats = async (params: {
    chat_id?: string
    date_from?: string
    date_to?: string
    top_emoji?: number
    top_terms?: number
  } = {}): Promise<VisualizationStatsResponse> => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    if (params.top_emoji) query.append('top_emoji', params.top_emoji.toString())
    if (params.top_terms) query.append('top_terms', params.top_terms.toString())

    const response = await fetch(`${await resolveBaseURL()}/api/stats/visualization?${query}`)
    if (!response.ok) throw new Error('Failed to fetch visualization stats')
    return response.json()
  }

  const getContactActivityStats = async (params: {
    chat_id?: string
    date_from?: string
    date_to?: string
    top_contacts?: number
    top_senders?: number
  } = {}): Promise<ContactActivityStatsResponse> => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    if (params.top_contacts) query.append('top_contacts', params.top_contacts.toString())
    if (params.top_senders) query.append('top_senders', params.top_senders.toString())

    const response = await fetch(`${await resolveBaseURL()}/api/stats/contacts?${query}`)
    if (!response.ok) throw new Error('Failed to fetch contact activity stats')
    return response.json()
  }

  const getRelationshipAnalysis = async (params: {
    chat_id?: string
    date_from?: string
    date_to?: string
    top_pairs?: number
    top_senders?: number
  } = {}): Promise<RelationshipAnalysisResponse> => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    if (params.top_pairs) query.append('top_pairs', params.top_pairs.toString())
    if (params.top_senders) query.append('top_senders', params.top_senders.toString())

    const response = await fetch(`${await resolveBaseURL()}/api/stats/relationships?${query}`)
    if (!response.ok) throw new Error('Failed to fetch relationship analysis')
    return response.json()
  }

  const getTopicClusters = async (params: {
    chat_id?: string
    date_from?: string
    date_to?: string
    top_terms?: number
    max_clusters?: number
  } = {}): Promise<TopicClustersResponse> => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    if (params.top_terms) query.append('top_terms', params.top_terms.toString())
    if (params.max_clusters) query.append('max_clusters', params.max_clusters.toString())

    const response = await fetch(`${await resolveBaseURL()}/api/stats/topics?${query}`)
    if (!response.ok) throw new Error('Failed to fetch topic clusters')
    return response.json()
  }

  const importJsonFile = async (file: File): Promise<ImportResponse> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${await resolveBaseURL()}/api/import`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) throw new Error(await response.text() || 'Failed to import file')
    return response.json()
  }

  const getAIStatus = async (): Promise<AIStatus> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/status`)
    if (!response.ok) throw new Error('Failed to fetch AI status')
    return response.json()
  }

  /** 获取当前 AI 配置（脱敏，API Key 仅返回是否已设置） */
  const getAIConfig = async (): Promise<Record<string, unknown>> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/config`)
    if (!response.ok) throw new Error('Failed to fetch AI config')
    return response.json()
  }

  /** 保存 AI 配置（写入本地配置文件，立即生效，无需重启） */
  const saveAIConfig = async (config: AIConfigUpdate): Promise<Record<string, unknown>> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `保存配置失败 (${response.status})`)
    }
    return response.json()
  }

  /** 清除 AI 运行时配置（恢复到环境变量 / 默认值） */
  const deleteAIConfig = async (): Promise<Record<string, unknown>> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/config`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('清除配置失败')
    return response.json()
  }

  /**
   * 测试 AI 连接：用临时 base_url + api_key 拉取模型列表并验证可用性。
   * 不依赖已保存配置，用户填完表单还没保存时即可测试。
   */
  const testAIConnection = async (params: {
    base_url: string
    api_key?: string
    provider?: string
    kind?: 'llm' | 'embedding'
  }): Promise<{ ok: boolean; models: string[]; latency_ms: number; error: string }> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_url: params.base_url,
        api_key: params.api_key || '',
        provider: params.provider || 'openai',
        kind: params.kind || 'llm',
      }),
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `测试失败 (${response.status})`)
    }
    return response.json()
  }

  const aiChat = async (params: {
    query: string
    chat_id?: string
    top_k?: number
    history?: Array<{ role: string; content: string }>
  }): Promise<AIChatResponse> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `AI chat failed (${response.status})`)
    }
    return response.json()
  }

  const aiSummary = async (params: {
    period: 'day' | 'week' | 'month'
    chat_id?: string
  }): Promise<AISummaryResponse> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `AI summary failed (${response.status})`)
    }
    return response.json()
  }

  const aiIndexStart = async (): Promise<{ started: boolean; message: string }> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/index`, { method: 'POST' })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `AI index start failed (${response.status})`)
    }
    return response.json()
  }

  const getAIIndexStatus = async (): Promise<IndexStatus> => {
    const response = await fetch(`${await resolveBaseURL()}/api/ai/index/status`)
    if (!response.ok) throw new Error('Failed to fetch index status')
    return response.json()
  }

  const buildExportUrl = async (params: {
    format: 'json' | 'csv' | 'report' | 'markdown' | 'html'
    chat_id?: string
    date_from?: string
    date_to?: string
    mask_sensitive?: boolean
    mask_terms?: string
    anonymize?: boolean
    encrypt_password?: string
    gpg_recipient?: string
  }): Promise<string> => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    if (params.mask_sensitive) query.append('mask_sensitive', 'true')
    if (params.mask_sensitive && params.mask_terms) query.append('mask_terms', params.mask_terms)
    if (params.anonymize) query.append('anonymize', 'true')
    if (params.encrypt_password) query.append('encrypt_password', params.encrypt_password)
    if (params.gpg_recipient) query.append('gpg_recipient', params.gpg_recipient)
    const suffix = query.toString()

    return `${await resolveBaseURL()}/api/export/${params.format}${suffix ? `?${suffix}` : ''}`
  }

  const exportMessages = async (params: {
    format: 'json' | 'csv' | 'report' | 'markdown' | 'html'
    chat_id?: string
    date_from?: string
    date_to?: string
    mask_sensitive?: boolean
    mask_terms?: string
    anonymize?: boolean
    encrypt_password?: string
    gpg_recipient?: string
  }): Promise<{ blob: Blob, filename: string }> => {
    const response = await fetch(await buildExportUrl(params))
    if (!response.ok) throw new Error(await response.text() || 'Failed to export messages')

    const disposition = response.headers.get('content-disposition') || ''
    const extensions = {
      json: 'json',
      csv: 'csv',
      report: 'json',
      markdown: 'md',
      html: 'html',
    }
    const encryptedExtension = params.encrypt_password ? 'lvenc' : `${extensions[params.format]}.gpg`
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] || `lifevault-export.${params.encrypt_password || params.gpg_recipient ? encryptedExtension : extensions[params.format]}`
    return {
      blob: await response.blob(),
      filename,
    }
  }

  return {
    getMessages,
    searchMessages,
    getStats,
    getVisualizationStats,
    getContactActivityStats,
    getRelationshipAnalysis,
    getTopicClusters,
    getAIStatus,
    getAIConfig,
    saveAIConfig,
    deleteAIConfig,
    testAIConnection,
    aiChat,
    aiSummary,
    aiIndexStart,
    getAIIndexStatus,
    importJsonFile,
    exportMessages,
  }
}
