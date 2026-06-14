import type {
  AIChatResponse,
  AISummaryResponse,
  AIStatus,
  ContactActivityStatsResponse,
  ImportResponse,
  IndexStatus,
  MessageListResponse,
  RelationshipAnalysisResponse,
  SearchResponse,
  StatsResponse,
  VisualizationStatsResponse,
} from '~/types/message'

export const useApi = () => {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase

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

    const response = await fetch(`${baseURL}/api/messages?${query}`)
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

    const response = await fetch(`${baseURL}/api/search?${query}`)
    if (!response.ok) throw new Error('Failed to search messages')
    return response.json()
  }

  const getStats = async (): Promise<StatsResponse> => {
    const response = await fetch(`${baseURL}/api/stats`)
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

    const response = await fetch(`${baseURL}/api/stats/visualization?${query}`)
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

    const response = await fetch(`${baseURL}/api/stats/contacts?${query}`)
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

    const response = await fetch(`${baseURL}/api/stats/relationships?${query}`)
    if (!response.ok) throw new Error('Failed to fetch relationship analysis')
    return response.json()
  }

  const importJsonFile = async (file: File): Promise<ImportResponse> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${baseURL}/api/import`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) throw new Error(await response.text() || 'Failed to import file')
    return response.json()
  }

  const getAIStatus = async (): Promise<AIStatus> => {
    const response = await fetch(`${baseURL}/api/ai/status`)
    if (!response.ok) throw new Error('Failed to fetch AI status')
    return response.json()
  }

  const aiChat = async (params: {
    query: string
    chat_id?: string
    top_k?: number
    history?: Array<{ role: string; content: string }>
  }): Promise<AIChatResponse> => {
    const response = await fetch(`${baseURL}/api/ai/chat`, {
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
    const response = await fetch(`${baseURL}/api/ai/summary`, {
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
    const response = await fetch(`${baseURL}/api/ai/index`, { method: 'POST' })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `AI index start failed (${response.status})`)
    }
    return response.json()
  }

  const getAIIndexStatus = async (): Promise<IndexStatus> => {
    const response = await fetch(`${baseURL}/api/ai/index/status`)
    if (!response.ok) throw new Error('Failed to fetch index status')
    return response.json()
  }

  const buildExportUrl = (params: {
    format: 'json' | 'csv' | 'report' | 'markdown' | 'html'
    chat_id?: string
    date_from?: string
    date_to?: string
    mask_sensitive?: boolean
    mask_terms?: string
    anonymize?: boolean
    encrypt_password?: string
    gpg_recipient?: string
  }): string => {
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

    return `${baseURL}/api/export/${params.format}${suffix ? `?${suffix}` : ''}`
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
    const response = await fetch(buildExportUrl(params))
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
    getAIStatus,
    aiChat,
    aiSummary,
    aiIndexStart,
    getAIIndexStatus,
    importJsonFile,
    exportMessages,
  }
}
