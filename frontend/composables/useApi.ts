import type { ImportResponse, MessageListResponse, SearchResponse, StatsResponse } from '~/types/message'

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

  const buildExportUrl = (params: {
    format: 'json' | 'csv' | 'report'
    chat_id?: string
    date_from?: string
    date_to?: string
  }): string => {
    const query = new URLSearchParams()
    if (params.chat_id) query.append('chat_id', params.chat_id)
    if (params.date_from) query.append('date_from', params.date_from)
    if (params.date_to) query.append('date_to', params.date_to)
    const suffix = query.toString()

    return `${baseURL}/api/export/${params.format}${suffix ? `?${suffix}` : ''}`
  }

  const exportMessages = async (params: {
    format: 'json' | 'csv' | 'report'
    chat_id?: string
    date_from?: string
    date_to?: string
  }): Promise<{ blob: Blob, filename: string }> => {
    const response = await fetch(buildExportUrl(params))
    if (!response.ok) throw new Error(await response.text() || 'Failed to export messages')

    const disposition = response.headers.get('content-disposition') || ''
    const filename = disposition.match(/filename="?([^";]+)"?/)?.[1] || `lifevault-export.${params.format === 'csv' ? 'csv' : 'json'}`
    return {
      blob: await response.blob(),
      filename,
    }
  }

  return {
    getMessages,
    searchMessages,
    getStats,
    importJsonFile,
    exportMessages,
  }
}
