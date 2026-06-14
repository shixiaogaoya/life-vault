<script setup lang="ts">
import type {
  ContactActivityStatsResponse,
  StatsResponse,
  VisualizationStatsResponse,
} from '~/types/message'

const { getStats, getVisualizationStats, getContactActivityStats } = useApi()

const stats = ref<StatsResponse | null>(null)
const vizStats = ref<VisualizationStatsResponse | null>(null)
const contactStats = ref<ContactActivityStatsResponse | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const filters = ref({
  chat_id: '',
  date_from: '',
  date_to: '',
})

const loadAll = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const [baseStats, visual, contacts] = await Promise.all([
      getStats(),
      getVisualizationStats({
        chat_id: filters.value.chat_id || undefined,
        date_from: filters.value.date_from || undefined,
        date_to: filters.value.date_to || undefined,
      }),
      getContactActivityStats({
        chat_id: filters.value.chat_id || undefined,
        date_from: filters.value.date_from || undefined,
        date_to: filters.value.date_to || undefined,
        top_contacts: 10,
        top_senders: 10,
      }),
    ])
    stats.value = baseStats
    vizStats.value = visual
    contactStats.value = contacts
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    loading.value = false
  }
}

const handleFilterChange = (newFilters: any) => {
  filters.value = newFilters
  loadAll()
}

onMounted(loadAll)

const peakHour = computed(() => {
  if (!vizStats.value) return null
  const arr = vizStats.value.hourly_distribution
  let maxIdx = 0
  for (let i = 1; i < arr.length; i++) {
    if (arr[i] > arr[maxIdx]) maxIdx = i
  }
  return arr[maxIdx] > 0 ? { hour: maxIdx, count: arr[maxIdx] } : null
})

const peakWeekday = computed(() => {
  if (!vizStats.value) return null
  const arr = vizStats.value.weekday_distribution
  const labels = vizStats.value.activity_heatmap.weekday_labels
  let maxIdx = 0
  for (let i = 1; i < arr.length; i++) {
    if (arr[i] > arr[maxIdx]) maxIdx = i
  }
  return arr[maxIdx] > 0 ? { label: labels[maxIdx], count: arr[maxIdx] } : null
})

const totalHeatmapMessages = computed(() => {
  if (!vizStats.value) return 0
  return vizStats.value.activity_heatmap.matrix.flat().reduce((a, b) => a + b, 0)
})

const totalHourly = computed(() => {
  if (!vizStats.value) return 0
  return vizStats.value.hourly_distribution.reduce((a, b) => a + b, 0)
})

const activeDays = computed(() => {
  if (!vizStats.value) return 0
  return vizStats.value.daily_timeseries.length
})

const hourlyBarHeights = computed(() => {
  if (!vizStats.value) return []
  const max = Math.max(...vizStats.value.hourly_distribution, 1)
  return vizStats.value.hourly_distribution.map((count) => ({
    count,
    height: (count / max) * 100,
  }))
})

const weekdayBarHeights = computed(() => {
  if (!vizStats.value) return []
  const labels = vizStats.value.activity_heatmap.weekday_labels
  const max = Math.max(...vizStats.value.weekday_distribution, 1)
  return vizStats.value.weekday_distribution.map((count, idx) => ({
    label: labels[idx],
    count,
    height: (count / max) * 100,
  }))
})

const mediaTypeEntries = computed(() => {
  if (!vizStats.value) return []
  const entries = Object.entries(vizStats.value.media_type_distribution)
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1
  return entries
    .map(([name, count]) => ({
      name,
      count,
      percentage: (count / total) * 100,
    }))
    .sort((a, b) => b.count - a.count)
})

const dailyTimeseriesPath = computed(() => {
  if (!vizStats.value || vizStats.value.daily_timeseries.length === 0) return ''
  const data = vizStats.value.daily_timeseries
  const maxCount = Math.max(...data.map((d) => d.count), 1)
  const width = 600
  const height = 120
  const padding = 10
  const stepX = (width - padding * 2) / Math.max(data.length - 1, 1)

  return data
    .map((d, i) => {
      const x = padding + i * stepX
      const y = height - padding - (d.count / maxCount) * (height - padding * 2)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
})

const dailyMaxCount = computed(() => {
  if (!vizStats.value || vizStats.value.daily_timeseries.length === 0) return 0
  return Math.max(...vizStats.value.daily_timeseries.map((d) => d.count))
})

// 热力图颜色：基于强度的灰蓝色梯度
const heatmapColor = (count: number, maxCount: number) => {
  if (count === 0 || maxCount === 0) return '#f3f4f6'
  const intensity = Math.log(count + 1) / Math.log(maxCount + 1)
  // 浅蓝 -> 深紫
  const hue = 220 - intensity * 40
  const lightness = 90 - intensity * 50
  return `hsl(${hue}, 65%, ${lightness}%)`
}

const formatNumber = (n: number) => n.toLocaleString()

const formatDate = (date: string) => {
  // YYYY-MM-DD -> M/D
  const [y, m, d] = date.split('-')
  return `${parseInt(m)}/${parseInt(d)}`
}

// ===== 对比视图：联系人活跃度 =====
const contactRankMaxCount = computed(() => {
  if (!contactStats.value || contactStats.value.top_contacts.length === 0) return 1
  return Math.max(...contactStats.value.top_contacts.map(c => c.message_count), 1)
})

const senderRankMaxCount = computed(() => {
  if (!contactStats.value || contactStats.value.top_senders.length === 0) return 1
  return Math.max(...contactStats.value.top_senders.map(s => s.message_count), 1)
})

// 堆叠图：取前 5 个聊天的每小时分布，找出全局最大值用于归一化
const hourlyStackMax = computed(() => {
  if (!contactStats.value) return 1
  let max = 0
  for (const item of contactStats.value.hourly_by_top_contacts) {
    for (const v of item.hourly) if (v > max) max = v
  }
  return Math.max(max, 1)
})

const hourlyStackColors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899']

const formatRelativeTime = (ts: number | null) => {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}
</script>

<template>
  <div class="dashboard-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-6xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">数据可视化仪表板</h1>
        <p class="text-gray-500 text-sm">基于消息时间、类型、发送者维度的多角度分析</p>
      </header>

      <FilterBar @filter-change="handleFilterChange" />

      <div v-if="errorMsg" class="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-4">
        {{ errorMsg }}
      </div>

      <div v-if="loading" class="text-center py-12 text-gray-500">加载中...</div>

      <div v-else-if="vizStats && stats" class="space-y-6">
        <section class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">总消息数</div>
            <div class="text-2xl font-bold text-blue-600 mt-1">{{ formatNumber(stats.total_messages) }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">活跃天数</div>
            <div class="text-2xl font-bold text-green-600 mt-1">{{ activeDays }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">最活跃时段</div>
            <div class="text-2xl font-bold text-purple-600 mt-1">
              <span v-if="peakHour">{{ peakHour.hour }}:00</span>
              <span v-else class="text-gray-400">-</span>
            </div>
            <div v-if="peakHour" class="text-xs text-gray-400 mt-1">{{ formatNumber(peakHour.count) }} 条</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">最活跃星期</div>
            <div class="text-2xl font-bold text-orange-600 mt-1">
              <span v-if="peakWeekday">{{ peakWeekday.label }}</span>
              <span v-else class="text-gray-400">-</span>
            </div>
            <div v-if="peakWeekday" class="text-xs text-gray-400 mt-1">{{ formatNumber(peakWeekday.count) }} 条</div>
          </div>
        </section>

        <section class="bg-white rounded-lg shadow p-5">
          <div class="flex items-baseline justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-900">活动热力图</h2>
            <span class="text-xs text-gray-500">星期 × 小时 (UTC{{ vizStats.timezone_offset >= 0 ? '+' : '' }}{{ vizStats.timezone_offset }})</span>
          </div>
          <div v-if="totalHeatmapMessages === 0" class="text-gray-400 text-center py-8">暂无数据</div>
          <div v-else class="overflow-x-auto">
            <div class="inline-block min-w-full">
              <div class="flex">
                <div class="w-12"></div>
                <div class="flex-1 grid gap-px text-[10px] text-gray-400"
                     style="grid-template-columns: repeat(24, minmax(0, 1fr));">
                  <div v-for="h in 24" :key="h" class="text-center">{{ (h - 1) % 6 === 0 ? (h - 1) : '' }}</div>
                </div>
              </div>
              <div v-for="(row, wIdx) in vizStats.activity_heatmap.matrix" :key="wIdx" class="flex items-center mb-px">
                <div class="w-12 text-xs text-gray-500 pr-2">{{ vizStats.activity_heatmap.weekday_labels[wIdx] }}</div>
                <div class="flex-1 grid gap-px"
                     style="grid-template-columns: repeat(24, minmax(0, 1fr));">
                  <div
                    v-for="(count, hIdx) in row"
                    :key="hIdx"
                    class="aspect-square rounded-sm relative group cursor-default"
                    :style="{ backgroundColor: heatmapColor(count, vizStats.activity_heatmap.max_count) }"
                  >
                    <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
                      {{ vizStats.activity_heatmap.weekday_labels[wIdx] }} {{ hIdx }}:00 · {{ count }} 条
                    </div>
                  </div>
                </div>
              </div>
              <div class="flex items-center justify-end mt-3 text-xs text-gray-500">
                <span class="mr-2">少</span>
                <div class="flex gap-px">
                  <div v-for="(c, idx) in [0, 0.25, 0.5, 0.75, 1]" :key="idx"
                       class="w-4 h-4 rounded-sm"
                       :style="{ backgroundColor: heatmapColor(Math.ceil(c * vizStats.activity_heatmap.max_count), vizStats.activity_heatmap.max_count) }">
                  </div>
                </div>
                <span class="ml-2">多</span>
              </div>
            </div>
          </div>
        </section>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <section class="bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">每小时分布</h2>
            <div v-if="totalHourly === 0" class="text-gray-400 text-center py-8">暂无数据</div>
            <div v-else class="flex items-end gap-px h-32">
              <div v-for="(item, idx) in hourlyBarHeights" :key="idx"
                   class="flex-1 group relative">
                <div class="bg-blue-500 rounded-t hover:bg-blue-600 transition-colors"
                     :style="{ height: `${item.height}%`, minHeight: item.count > 0 ? '2px' : '0' }">
                </div>
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
                  {{ idx }}:00 · {{ item.count }} 条
                </div>
              </div>
            </div>
            <div class="flex justify-between mt-2 text-[10px] text-gray-400">
              <span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
            </div>
          </section>

          <section class="bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">每周分布</h2>
            <div v-if="totalHourly === 0" class="text-gray-400 text-center py-8">暂无数据</div>
            <div v-else class="flex items-end gap-3 h-32 justify-around">
              <div v-for="(item, idx) in weekdayBarHeights" :key="idx"
                   class="flex-1 max-w-[60px] group relative">
                <div class="bg-emerald-500 rounded-t hover:bg-emerald-600 transition-colors"
                     :style="{ height: `${item.height}%`, minHeight: item.count > 0 ? '2px' : '0' }">
                </div>
                <div class="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
                  {{ item.label }} · {{ item.count }} 条
                </div>
                <div class="text-xs text-gray-500 text-center mt-2">{{ item.label }}</div>
              </div>
            </div>
          </section>
        </div>

        <section class="bg-white rounded-lg shadow p-5">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">每日消息趋势</h2>
          <div v-if="vizStats.daily_timeseries.length === 0" class="text-gray-400 text-center py-8">暂无数据</div>
          <div v-else>
            <svg viewBox="0 0 600 140" class="w-full h-32">
              <defs>
                <linearGradient :id="`area-grad`" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="rgba(99, 102, 241, 0.4)" />
                  <stop offset="100%" stop-color="rgba(99, 102, 241, 0)" />
                </linearGradient>
              </defs>
              <path
                v-if="dailyTimeseriesPath"
                :d="`${dailyTimeseriesPath} L590,130 L10,130 Z`"
                :fill="`url(#area-grad)`"
              />
              <path
                v-if="dailyTimeseriesPath"
                :d="dailyTimeseriesPath"
                fill="none"
                stroke="rgb(79, 70, 229)"
                stroke-width="2"
                stroke-linejoin="round"
                stroke-linecap="round"
              />
              <text x="10" y="12" font-size="10" fill="#9ca3af">峰值 {{ dailyMaxCount }}</text>
            </svg>
            <div class="flex justify-between text-[10px] text-gray-400 mt-1">
              <span v-if="vizStats.daily_timeseries.length > 0">
                {{ formatDate(vizStats.daily_timeseries[0].date) }}
              </span>
              <span v-if="vizStats.daily_timeseries.length > 0">
                {{ formatDate(vizStats.daily_timeseries[vizStats.daily_timeseries.length - 1].date) }}
              </span>
            </div>
          </div>
        </section>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <section class="bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">媒体类型分布</h2>
            <div v-if="mediaTypeEntries.length === 0" class="text-gray-400 text-center py-8">暂无数据</div>
            <ul v-else class="space-y-2">
              <li v-for="item in mediaTypeEntries" :key="item.name" class="flex items-center gap-3">
                <span class="text-sm text-gray-700 w-20 truncate">{{ item.name }}</span>
                <div class="flex-1 bg-gray-100 rounded h-4 overflow-hidden">
                  <div class="h-full bg-gradient-to-r from-indigo-400 to-indigo-600"
                       :style="{ width: `${item.percentage}%` }"></div>
                </div>
                <span class="text-xs text-gray-500 w-16 text-right">{{ formatNumber(item.count) }}</span>
              </li>
            </ul>
          </section>

          <section class="bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">高频词 Top 10</h2>
            <div v-if="vizStats.top_terms.length === 0" class="text-gray-400 text-center py-8">暂无数据</div>
            <div v-else class="flex flex-wrap gap-2">
              <span
                v-for="(item, idx) in vizStats.top_terms.slice(0, 10)"
                :key="idx"
                class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
                :class="idx < 3 ? 'bg-amber-100 text-amber-800' : 'bg-indigo-100 text-indigo-800'"
              >
                {{ item.term }}
                <span class="ml-1 text-xs opacity-70">{{ item.count }}</span>
              </span>
            </div>
          </section>

          <section class="bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Emoji Top 10</h2>
            <div v-if="vizStats.emoji_stats.length === 0" class="text-gray-400 text-center py-8">暂无数据</div>
            <ul v-else class="space-y-2">
              <li v-for="(item, idx) in vizStats.emoji_stats.slice(0, 10)" :key="idx"
                  class="flex items-center gap-3">
                <span class="text-2xl">{{ item.emoji }}</span>
                <div class="flex-1 bg-gray-100 rounded h-3 overflow-hidden">
                  <div class="h-full bg-pink-400"
                       :style="{ width: `${(item.count / vizStats.emoji_stats[0].count) * 100}%` }"></div>
                </div>
                <span class="text-xs text-gray-500 w-12 text-right">{{ item.count }}</span>
              </li>
            </ul>
          </section>
        </div>

        <section class="bg-white rounded-lg shadow p-5">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">发送 / 接收比例</h2>
          <div class="flex items-center gap-6">
            <div class="flex-1">
              <div class="flex h-8 rounded overflow-hidden">
                <div class="bg-blue-500 flex items-center justify-center text-white text-sm font-medium"
                     :style="{ width: `${vizStats.sender_receiver_ratio.sent_percentage}%` }">
                  <span v-if="vizStats.sender_receiver_ratio.sent_percentage >= 10">
                    发送 {{ vizStats.sender_receiver_ratio.sent_percentage }}%
                  </span>
                </div>
                <div class="bg-gray-300 flex items-center justify-center text-gray-700 text-sm font-medium"
                     :style="{ width: `${100 - vizStats.sender_receiver_ratio.sent_percentage}%` }">
                  <span v-if="100 - vizStats.sender_receiver_ratio.sent_percentage >= 10">
                    接收 {{ (100 - vizStats.sender_receiver_ratio.sent_percentage).toFixed(2) }}%
                  </span>
                </div>
              </div>
            </div>
              <div class="text-right">
              <div class="text-xs text-gray-500">总互动</div>
              <div class="text-lg font-bold text-gray-900">
                {{ formatNumber(vizStats.sender_receiver_ratio.sent + vizStats.sender_receiver_ratio.received) }}
              </div>
            </div>
          </div>
        </section>

        <section v-if="contactStats" class="bg-white rounded-lg shadow p-5">
          <div class="flex items-baseline justify-between mb-4 flex-wrap gap-2">
            <h2 class="text-lg font-semibold text-gray-900">联系人活跃度对比</h2>
            <span class="text-xs text-gray-500">
              {{ contactStats.total_contacts }} 个聊天 · {{ contactStats.total_senders }} 位发送者
            </span>
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 class="text-sm font-medium text-gray-700 mb-3">聊天排名（Top {{ contactStats.top_contacts.length }}）</h3>
              <div v-if="contactStats.top_contacts.length === 0" class="text-gray-400 text-center py-6 text-sm">暂无数据</div>
              <ul v-else class="space-y-2">
                <li v-for="(item, idx) in contactStats.top_contacts" :key="item.chat_id"
                    class="flex items-center gap-3">
                  <span class="text-xs text-gray-400 w-5 text-right">{{ idx + 1 }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex justify-between text-xs mb-1">
                      <span class="text-gray-700 truncate">{{ item.chat_name }}</span>
                      <span class="text-gray-500 ml-2 shrink-0">{{ formatNumber(item.message_count) }}</span>
                    </div>
                    <div class="flex h-3 rounded overflow-hidden bg-gray-100">
                      <div class="bg-blue-500"
                           :style="{ width: `${(item.received / contactRankMaxCount) * 100}%` }"
                           :title="`接收 ${item.received}`"></div>
                      <div class="bg-emerald-500"
                           :style="{ width: `${(item.sent / contactRankMaxCount) * 100}%` }"
                           :title="`发送 ${item.sent}`"></div>
                    </div>
                    <div class="text-[10px] text-gray-400 mt-0.5">
                      {{ formatRelativeTime(item.first_seen) }} ~ {{ formatRelativeTime(item.last_seen) }}
                    </div>
                  </div>
                </li>
              </ul>
              <div class="flex items-center gap-4 mt-3 text-[10px] text-gray-500">
                <span class="flex items-center gap-1"><span class="inline-block w-2 h-2 bg-emerald-500 rounded-sm"></span>发送</span>
                <span class="flex items-center gap-1"><span class="inline-block w-2 h-2 bg-blue-500 rounded-sm"></span>接收</span>
              </div>
            </div>

            <div>
              <h3 class="text-sm font-medium text-gray-700 mb-3">发送者排名（Top {{ contactStats.top_senders.length }}）</h3>
              <div v-if="contactStats.top_senders.length === 0" class="text-gray-400 text-center py-6 text-sm">暂无数据</div>
              <ul v-else class="space-y-2">
                <li v-for="(item, idx) in contactStats.top_senders" :key="item.sender_name + idx"
                    class="flex items-center gap-3">
                  <span class="text-xs text-gray-400 w-5 text-right">{{ idx + 1 }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex justify-between text-xs mb-1">
                      <span class="text-gray-700 truncate">{{ item.sender_name }}</span>
                      <span class="text-gray-500 ml-2 shrink-0">{{ formatNumber(item.message_count) }}</span>
                    </div>
                    <div class="bg-gray-100 rounded h-2 overflow-hidden">
                      <div class="h-full bg-indigo-500"
                           :style="{ width: `${(item.message_count / senderRankMaxCount) * 100}%` }"></div>
                    </div>
                    <div class="text-[10px] text-gray-400 mt-0.5">
                      参与 {{ item.distinct_chats }} 个聊天
                    </div>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section v-if="contactStats && contactStats.hourly_by_top_contacts.length > 0"
                 class="bg-white rounded-lg shadow p-5">
          <h2 class="text-lg font-semibold text-gray-900 mb-1">活跃时段对比</h2>
          <p class="text-xs text-gray-500 mb-4">前 {{ contactStats.hourly_by_top_contacts.length }} 个聊天的小时分布</p>
          <div class="space-y-3">
            <div v-for="(item, idx) in contactStats.hourly_by_top_contacts" :key="item.chat_id"
                 class="flex items-center gap-3">
              <div class="w-24 text-xs text-gray-700 truncate shrink-0">
                <span class="inline-block w-3 h-3 rounded-sm mr-1 align-middle"
                      :style="{ backgroundColor: hourlyStackColors[idx % hourlyStackColors.length] }"></span>
                {{ item.chat_name }}
              </div>
              <div class="flex-1 flex items-end gap-px h-10">
                <div v-for="(count, hIdx) in item.hourly" :key="hIdx"
                     class="flex-1 rounded-t group relative"
                     :style="{
                       height: `${(count / hourlyStackMax) * 100}%`,
                       minHeight: count > 0 ? '2px' : '0',
                       backgroundColor: hourlyStackColors[idx % hourlyStackColors.length],
                     }">
                  <div v-if="count > 0"
                       class="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
                    {{ hIdx }}:00 · {{ count }} 条
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="flex justify-between mt-2 text-[10px] text-gray-400 pl-24">
            <span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
