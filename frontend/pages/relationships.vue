<script setup lang="ts">
import type { RelationshipAnalysisResponse } from '~/types/message'

const { getRelationshipAnalysis } = useApi()

const data = ref<RelationshipAnalysisResponse | null>(null)
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
    data.value = await getRelationshipAnalysis({
      chat_id: filters.value.chat_id || undefined,
      date_from: filters.value.date_from || undefined,
      date_to: filters.value.date_to || undefined,
      top_pairs: 30,
      top_senders: 20,
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

// ===== 圆形布局：把节点均匀分布在圆周上，连线表示关系 =====
const SVG_SIZE = 560
const SVG_CENTER = SVG_SIZE / 2
const SVG_RADIUS = 200

interface LayoutNode {
  name: string
  message_count: number
  chat_count: number
  x: number
  y: number
  r: number
}

const layoutNodes = computed<LayoutNode[]>(() => {
  if (!data.value || data.value.sender_nodes.length === 0) return []
  const nodes = data.value.sender_nodes
  const maxCount = Math.max(...nodes.map((n) => n.message_count), 1)
  const n = nodes.length
  return nodes.map((node, idx) => {
    // 单节点放中心，否则均匀分布在圆周
    let x: number, y: number
    if (n === 1) {
      x = SVG_CENTER
      y = SVG_CENTER
    } else {
      const angle = (2 * Math.PI * idx) / n - Math.PI / 2
      x = SVG_CENTER + SVG_RADIUS * Math.cos(angle)
      y = SVG_CENTER + SVG_RADIUS * Math.sin(angle)
    }
    // 节点半径根据消息量缩放（8 ~ 26）
    const r = 8 + (node.message_count / maxCount) * 18
    return { ...node, x, y, r }
  })
})

const nodeByName = computed<Map<string, LayoutNode>>(() => {
  const m = new Map<string, LayoutNode>()
  for (const n of layoutNodes.value) m.set(n.name, n)
  return m
})

const maxStrength = computed(() => {
  if (!data.value || data.value.edges.length === 0) return 1
  return Math.max(...data.value.edges.map((e) => e.strength), 1)
})

const layoutEdges = computed(() => {
  if (!data.value) return []
  const result: { x1: number; y1: number; x2: number; y2: number; strength: number; width: number }[] = []
  for (const edge of data.value.edges) {
    const a = nodeByName.value.get(edge.source)
    const b = nodeByName.value.get(edge.target)
    if (!a || !b) continue
    const width = 0.5 + (edge.strength / maxStrength.value) * 4
    result.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, strength: edge.strength, width })
  }
  return result
})

// 节点颜色：按消息量取色阶
const nodeColor = (count: number) => {
  const max = Math.max(...(data.value?.sender_nodes.map((n) => n.message_count) ?? [1]), 1)
  const intensity = count / max
  const hue = 210 - intensity * 30
  const lightness = 70 - intensity * 25
  return `hsl(${hue}, 70%, ${lightness}%)`
}

const hasGraph = computed(() => layoutNodes.value.length > 0)
</script>

<template>
  <div class="relationships-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-6xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-2">关系图谱</h1>
        <p class="text-gray-500 text-sm">
          基于共同聊天出现的发送者关系网络。两个发送者在同一聊天中都发过消息即视为有关系。
        </p>
      </header>

      <FilterBar @filter-change="handleFilterChange" />

      <div v-if="errorMsg" class="bg-red-50 border border-red-200 text-red-700 p-3 rounded mb-4">
        {{ errorMsg }}
      </div>

      <div v-if="loading" class="text-center py-12 text-gray-500">加载中...</div>

      <div v-else-if="data" class="space-y-6">
        <!-- 概览卡片 -->
        <section class="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">发送者总数</div>
            <div class="text-2xl font-bold text-blue-600 mt-1">{{ data.total_senders }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">群聊数量（多人）</div>
            <div class="text-2xl font-bold text-green-600 mt-1">{{ data.total_group_chats }}</div>
          </div>
          <div class="bg-white rounded-lg shadow p-4">
            <div class="text-xs text-gray-500">关系对数量</div>
            <div class="text-2xl font-bold text-purple-600 mt-1">{{ data.top_pairs.length }}</div>
          </div>
        </section>

        <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <!-- 关系图（占 3 列） -->
          <section class="lg:col-span-3 bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-1">关系网络图</h2>
            <p class="text-xs text-gray-500 mb-4">
              节点大小 = 消息量；连线粗细 = 关系强度（共同聊天数 × 10 + 消息总量）
            </p>
            <div v-if="!hasGraph" class="text-gray-400 text-center py-16">
              暂无可分析的关系数据。需要至少两个发送者在同一聊天中出现。
            </div>
            <svg v-else :viewBox="`0 0 ${SVG_SIZE} ${SVG_SIZE}`" class="w-full" style="max-height: 560px;">
              <!-- 边 -->
              <g v-for="(edge, idx) in layoutEdges" :key="`edge-${idx}`">
                <line
                  :x1="edge.x1" :y1="edge.y1" :x2="edge.x2" :y2="edge.y2"
                  :stroke-width="edge.width"
                  stroke="rgba(99, 102, 241, 0.4)"
                  stroke-linecap="round"
                />
              </g>
              <!-- 节点 -->
              <g v-for="(node, idx) in layoutNodes" :key="`node-${idx}`">
                <circle
                  :cx="node.x" :cy="node.y" :r="node.r"
                  :fill="nodeColor(node.message_count)"
                  stroke="white" stroke-width="2"
                />
                <text
                  :x="node.x" :y="node.y + node.r + 14"
                  text-anchor="middle"
                  font-size="11" fill="#374151"
                >{{ node.name }}</text>
                <title>{{ node.name }} · {{ node.message_count }} 条消息 · {{ node.chat_count }} 个聊天</title>
              </g>
            </svg>
          </section>

          <!-- 关系对排名（占 2 列） -->
          <section class="lg:col-span-2 bg-white rounded-lg shadow p-5">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">关系强度排行</h2>
            <div v-if="data.top_pairs.length === 0" class="text-gray-400 text-center py-8 text-sm">
              暂无关系对
            </div>
            <ul v-else class="space-y-2">
              <li v-for="(pair, idx) in data.top_pairs" :key="idx" class="bg-gray-50 rounded p-3">
                <div class="flex items-center justify-between mb-1">
                  <div class="text-sm font-medium text-gray-900">
                    <span class="text-blue-600">{{ pair.a }}</span>
                    <span class="text-gray-400 mx-1">↔</span>
                    <span class="text-emerald-600">{{ pair.b }}</span>
                  </div>
                  <span class="text-xs text-gray-400">#{{ idx + 1 }}</span>
                </div>
                <div class="bg-gray-200 rounded h-2 overflow-hidden mb-2">
                  <div class="h-full bg-gradient-to-r from-indigo-400 to-purple-500"
                       :style="{ width: `${(pair.strength / maxStrength) * 100}%` }"></div>
                </div>
                <div class="flex justify-between text-[10px] text-gray-500">
                  <span>共同聊天 {{ pair.shared_chats }}</span>
                  <span>消息量 {{ pair.message_volume }}</span>
                  <span>强度 {{ pair.strength }}</span>
                </div>
              </li>
            </ul>
          </section>
        </div>

        <!-- 节点详情表 -->
        <section v-if="data.sender_nodes.length > 0" class="bg-white rounded-lg shadow p-5">
          <h2 class="text-lg font-semibold text-gray-900 mb-4">参与者详情</h2>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-left text-xs text-gray-500 border-b">
                  <th class="pb-2 pr-4">发送者</th>
                  <th class="pb-2 pr-4 text-right">消息数</th>
                  <th class="pb-2 pr-4 text-right">参与聊天数</th>
                  <th class="pb-2 text-right">关系数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="node in data.sender_nodes" :key="node.name" class="border-b border-gray-100">
                  <td class="py-2 pr-4 font-medium text-gray-900">{{ node.name }}</td>
                  <td class="py-2 pr-4 text-right text-gray-700">{{ node.message_count.toLocaleString() }}</td>
                  <td class="py-2 pr-4 text-right text-gray-700">{{ node.chat_count }}</td>
                  <td class="py-2 text-right text-gray-700">
                    {{ data.edges.filter(e => e.source === node.name || e.target === node.name).length }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
