<script setup lang="ts">
import type { TopicClustersResponse } from '~/types/message'

const { getTopicClusters } = useApi()

const data = ref<TopicClustersResponse | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const filters = ref({
  chat_id: '',
  date_from: '',
  date_to: '',
})

const loadData = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    data.value = await getTopicClusters({
      chat_id: filters.value.chat_id || undefined,
      date_from: filters.value.date_from || undefined,
      date_to: filters.value.date_to || undefined,
      top_terms: 50,
      max_clusters: 10,
    })
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

const handleFilterChange = (newFilters: any) => {
  filters.value = newFilters
  loadData()
}

onMounted(loadData)

// 每个簇的颜色调色板
const clusterColors = [
  { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', chip: 'bg-blue-100 text-blue-700', bar: 'bg-blue-500' },
  { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', chip: 'bg-emerald-100 text-emerald-700', bar: 'bg-emerald-500' },
  { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', chip: 'bg-amber-100 text-amber-700', bar: 'bg-amber-500' },
  { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-800', chip: 'bg-purple-100 text-purple-700', bar: 'bg-purple-500' },
  { bg: 'bg-pink-50', border: 'border-pink-200', text: 'text-pink-800', chip: 'bg-pink-100 text-pink-700', bar: 'bg-pink-500' },
  { bg: 'bg-cyan-50', border: 'border-cyan-200', text: 'text-cyan-800', chip: 'bg-cyan-100 text-cyan-700', bar: 'bg-cyan-500' },
  { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-800', chip: 'bg-indigo-100 text-indigo-700', bar: 'bg-indigo-500' },
  { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-800', chip: 'bg-rose-100 text-rose-700', bar: 'bg-rose-500' },
  { bg: 'bg-teal-50', border: 'border-teal-200', text: 'text-teal-800', chip: 'bg-teal-100 text-teal-700', bar: 'bg-teal-500' },
  { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-800', chip: 'bg-orange-100 text-orange-700', bar: 'bg-orange-500' },
]

const colorFor = (idx: number) => clusterColors[idx % clusterColors.length]

const maxMessageCount = computed(() => {
  if (!data.value || data.value.clusters.length === 0) return 1
  return Math.max(...data.value.clusters.map(c => c.message_count), 1)
})

const formatNumber = (n: number) => n.toLocaleString()
const formatPercent = (count: number, total: number) => {
  if (total === 0) return '0.0'
  return ((count / total) * 100).toFixed(1)
}
</script>

<template>
  <div class="topics-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-6xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">话题聚类</h1>
        <p class="text-gray-500 text-sm">
          基于关键词共现的轻量级话题发现。反复一起出现的关键词会被归为同一话题簇。
        </p>
      </header>

      <FilterBar @filter-change="handleFilterChange" />

      <div v-if="errorMsg" class="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-4">
        {{ errorMsg }}
      </div>

      <div v-if="loading" class="text-center py-12 text-gray-500">加载中...</div>

      <div v-else-if="data" class="space-y-6">
        <!-- 概览 -->
        <section class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">分析消息数</div>
            <div class="text-2xl font-bold text-blue-600 mt-1">{{ formatNumber(data.total_messages) }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">候选关键词</div>
            <div class="text-2xl font-bold text-green-600 mt-1">{{ formatNumber(data.total_terms) }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">话题簇数</div>
            <div class="text-2xl font-bold text-purple-600 mt-1">{{ data.clusters.length }}</div>
          </div>
        </section>

        <!-- 簇列表 -->
        <section v-if="data.clusters.length === 0" class="bg-white rounded-lg shadow p-8 text-center">
          <div class="text-4xl mb-3">📭</div>
          <h2 class="text-xl font-semibold text-gray-900 mb-2">暂无话题</h2>
          <p class="text-gray-500 text-sm">
            没有足够的文本消息用于话题分析。导入更多聊天记录后再试。
          </p>
        </section>

        <section v-else class="space-y-4">
          <div
            v-for="(cluster, idx) in data.clusters"
            :key="cluster.id"
            class="bg-white rounded-lg shadow p-5 border-l-4"
            :class="colorFor(idx).border.replace('border-', 'border-l-')"
          >
            <div class="flex items-baseline justify-between mb-3 flex-wrap gap-2">
              <div class="flex items-center gap-2">
                <span class="text-xs font-mono text-gray-400">#{{ cluster.id + 1 }}</span>
                <h2 class="text-lg font-semibold text-gray-900">{{ cluster.label }}</h2>
                <span class="text-xs text-gray-400">({{ cluster.term_count }} 个关键词)</span>
              </div>
              <div class="text-right">
                <div class="text-sm font-bold text-gray-900">
                  {{ formatNumber(cluster.message_count) }} 条消息
                </div>
                <div class="text-xs text-gray-500">
                  覆盖 {{ formatPercent(cluster.message_count, data.total_messages) }}% 文本
                </div>
              </div>
            </div>

            <!-- 覆盖度条 -->
            <div class="bg-gray-100 rounded h-2 overflow-hidden mb-4">
              <div
                class="h-full transition-all"
                :class="colorFor(idx).bar"
                :style="{ width: `${(cluster.message_count / maxMessageCount) * 100}%` }"
              ></div>
            </div>

            <!-- 关键词标签 -->
            <div class="flex flex-wrap gap-2">
              <span
                v-for="(kw, kwIdx) in cluster.keywords"
                :key="kwIdx"
                class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
                :class="colorFor(idx).chip"
              >
                {{ kw }}
              </span>
            </div>
          </div>
        </section>

        <!-- 算法说明 -->
        <section class="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-600">
          <strong>算法说明：</strong>
          本功能不依赖第三方 NLP 库。流程为：提取中文 2/3-gram 与英文词作为候选关键词 →
          按文档频率取 Top N → 构建共现图（两词在同一条消息中出现则连边）→
          用并查集按共现强度分簇。适用于个人规模的快速话题概览，
          精度不如专业分词/主题模型，但零依赖、可本地运行。
        </section>
      </div>
    </div>
  </div>
</template>
