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

export interface ActivityHeatmap {
  matrix: number[][]  // 7x24 [weekday][hour]
  max_count: number
  weekday_labels: string[]
  hour_labels: string[]
}

export interface EmojiStatItem {
  emoji: string
  count: number
}

export interface TermStatItem {
  term: string
  count: number
}

export interface DailyTimeseriesItem {
  date: string
  count: number
}

export interface VisualizationStatsResponse {
  activity_heatmap: ActivityHeatmap
  hourly_distribution: number[]
  weekday_distribution: number[]
  daily_timeseries: DailyTimeseriesItem[]
  emoji_stats: EmojiStatItem[]
  top_terms: TermStatItem[]
  media_type_distribution: Record<string, number>
  sender_receiver_ratio: {
    sent: number
    received: number
    sent_percentage: number
  }
  timezone_offset: number
}

export interface ContactActivityItem {
  chat_id: string
  chat_name: string
  message_count: number
  first_seen: number | null
  last_seen: number | null
  sent: number
  received: number
  text_count: number
  media_count: number
}

export interface SenderActivityItem {
  sender_name: string
  message_count: number
  sent: number
  received: number
  distinct_chats: number
}

export interface HourlyByContactItem {
  chat_id: string
  chat_name: string
  hourly: number[]
}

export interface ContactActivityStatsResponse {
  total_contacts: number
  total_senders: number
  top_contacts: ContactActivityItem[]
  top_senders: SenderActivityItem[]
  hourly_by_top_contacts: HourlyByContactItem[]
}

export interface AIStatus {
  llm_enabled: boolean
  llm_provider: string
  llm_model: string
  llm_data_flows_remote: boolean
  embedding_enabled: boolean
  embedding_provider: string
  embedding_model: string
  is_local_only: boolean
  index_progress: {
    status: string
    total: number
    processed: number
    failed: number
    started_at: string
    finished_at: string
    error: string
  }
}

export interface ChatCitation {
  message_id: number
  chunk_text: string
  score: number
  chat_id: string
  timestamp: number
  chat_name: string
  sender_name: string
}

export interface ChatMessageItem {
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: ChatCitation[]
}

export interface AIChatResponse {
  answer: string
  citations: ChatCitation[]
  model: string
  usage: Record<string, number>
}

export interface AISummaryResponse {
  summary: string
  period: string
  chat_id: string | null
  message_count: number
  chunks_processed: number
  model: string
}

export interface IndexStatus {
  status: string
  total: number
  processed: number
  failed: number
  started_at: string
  finished_at: string
  error: string
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
