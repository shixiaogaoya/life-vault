export interface UnifiedMessage {
  id: number
  source: string
  msg_svr_id: number
  local_id: number
  msg_type: number
  sub_type: number
  timestamp: number
  created_at: string
  updated_at: string
  chat_id: string
  chat_name: string
  sender_id: string
  sender_name: string
  is_sender: boolean
  content: string
  status: number
  raw: Record<string, any>
  metadata: Record<string, any>
  type_name?: string
}

export interface MessageListResponse {
  total: number
  page: number
  page_size: number
  messages: UnifiedMessage[]
}

export interface SearchResponse {
  total: number
  page: number
  page_size: number
  query: string
  results: UnifiedMessage[]
}

export interface StatsResponse {
  total_messages: number
  sources: Record<string, number>
  earliest_message: number | null
  latest_message: number | null
  chat_count: number
  top_chats: Array<{
    chat_id: string
    chat_name: string
    message_count: number
  }>
}
