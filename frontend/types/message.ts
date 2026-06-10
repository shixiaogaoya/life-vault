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

export interface MessageListItem {
  id: number
  msg_type: number
  sub_type: number
  timestamp: number
  chat_id: string
  chat_name: string
  sender_name: string
  is_sender: boolean
  content: string
  type_name: string
}

export interface SearchResultItem {
  id: number
  timestamp: number
  chat_name: string
  sender_name: string
  content: string
  snippet: string
  type_name: string
}

export interface MessageListResponse {
  total: number
  page: number
  page_size: number
  messages: MessageListItem[]
}

export interface SearchResponse {
  total: number
  page: number
  page_size: number
  query: string
  results: SearchResultItem[]
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

export interface ImportResponse {
  success: boolean
  total_messages: number
  imported: number
  failed: number
  errors: Array<{
    local_id: number | null
    error_type: string
    error_message: string
  }>
}
