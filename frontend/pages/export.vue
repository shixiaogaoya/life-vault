<script setup lang="ts">
const { exportMessages } = useApi()

const exportOptions = ref({
  format: 'json' as 'json' | 'csv' | 'report' | 'markdown' | 'html',
  chat_id: '',
  date_from: '',
  date_to: '',
  mask_sensitive: false,
  mask_terms: '',
})

const exportTask = ref<{
  status: 'processing' | 'completed' | 'failed'
  file_url?: string
  filename?: string
  error?: string
} | null>(null)
const exporting = ref(false)

const startExport = async () => {
  exporting.value = true
  exportTask.value = {
    status: 'processing',
  }

  try {
    const result = await exportMessages(exportOptions.value)
    if (exportTask.value?.file_url) {
      URL.revokeObjectURL(exportTask.value.file_url)
    }
    exportTask.value = {
      status: 'completed',
      file_url: URL.createObjectURL(result.blob),
      filename: result.filename,
    }
  } catch (error) {
    exportTask.value = {
      status: 'failed',
      error: error instanceof Error ? error.message : '导出失败',
    }
  } finally {
    exporting.value = false
  }
}

onBeforeUnmount(() => {
  if (exportTask.value?.file_url) {
    URL.revokeObjectURL(exportTask.value.file_url)
  }
})
</script>

<template>
  <div class="export-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-2xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-4">导出数据</h1>
      </header>

      <div class="export-form bg-white rounded-lg shadow p-6 mb-6">
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">导出格式</label>
          <select
            v-model="exportOptions.format"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="report">JSON 分析报告</option>
            <option value="markdown">Markdown 聊天记录</option>
            <option value="html">HTML 分析报告</option>
          </select>
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">联系人 ID（可选）</label>
          <input
            v-model="exportOptions.chat_id"
            type="text"
            placeholder="留空导出全部"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
        </div>

        <div class="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">开始日期（可选）</label>
            <input
              v-model="exportOptions.date_from"
              type="date"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">结束日期（可选）</label>
            <input
              v-model="exportOptions.date_to"
              type="date"
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
          </div>
        </div>

        <div class="mb-4 rounded-md border border-gray-200 p-4">
          <label class="flex items-center gap-2 text-sm font-medium text-gray-700">
            <input
              v-model="exportOptions.mask_sensitive"
              type="checkbox"
              class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            >
            导出前脱敏
          </label>

          <textarea
            v-model="exportOptions.mask_terms"
            :disabled="!exportOptions.mask_sensitive"
            rows="3"
            placeholder="可选：输入要额外脱敏的人名、地址等，用逗号或换行分隔"
            class="mt-3 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
          ></textarea>
        </div>

        <button
          class="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
          :disabled="exporting"
          @click="startExport"
        >
          {{ exporting ? '导出中...' : '开始导出' }}
        </button>
      </div>

      <div v-if="exportTask" class="export-status bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold mb-4">导出状态</h2>

        <div v-if="exportTask.status === 'processing'" class="text-center py-4">
          <div class="text-blue-600 mb-2">处理中...</div>
          <div class="text-sm text-gray-500">正在生成导出文件</div>
        </div>

        <div v-if="exportTask.status === 'completed'" class="text-center py-4">
          <div class="text-green-600 mb-4">✓ 导出完成</div>
          <a
            :href="exportTask.file_url"
            :download="exportTask.filename"
            class="inline-block px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            下载文件
          </a>
        </div>

        <div v-if="exportTask.status === 'failed'" class="text-center py-4">
          <div class="text-red-600 mb-2">导出失败</div>
          <div class="text-sm text-gray-500">{{ exportTask.error }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
