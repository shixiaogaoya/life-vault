import type { MessageListResponse, SearchResponse, StatsResponse } from '~/types/message'

export const useApi = () => {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase

  const getMessages = async (params: {
    page?: number
    page_size?: number
    chat_id?: string
    date_from?: string
    date_to?: string
  } = ): Promise<MessageListResponse> => {
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

  return {
    getMessages,
    searchMessages,
    getStats,
  }
}
