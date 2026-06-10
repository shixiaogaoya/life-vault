<script setup lang="ts">
const { importJsonFile } = useApi()

const selectedFile = ref<File | null>(null)
const importing = ref(false)
const result = ref<Awaited<ReturnType<typeof importJsonFile>> | null>(null)
const errorMessage = ref('')

const handleFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
  result.value = null
  errorMessage.value = ''
}

const startImport = async () => {
  if (!selectedFile.value) {
    errorMessage.value = '请选择 JSON 数据文件'
    return
  }

  importing.value = true
  errorMessage.value = ''
  result.value = null

  try {
    result.value = await importJsonFile(selectedFile.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导入失败'
  } finally {
    importing.value = false
  }
}
</script>

<template>
  <div class="import-page min-h-screen bg-gray-50 p-6">
    <div class="max-w-2xl mx-auto">
      <header class="mb-6">
        <h1 class="text-3xl font-bold text-gray-900 mb-4">导入数据</h1>
      </header>

      <div class="bg-white rounded-lg shadow p-6 mb-6">
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">LifeVault JSON 文件</label>
          <input
            type="file"
            accept="application/json,.json"
            class="block w-full text-sm text-gray-700 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
            @change="handleFileChange"
          >
        </div>

        <button
          class="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-400"
          :disabled="importing || !selectedFile"
          @click="startImport"
        >
          {{ importing ? '导入中...' : '开始导入' }}
        </button>
      </div>

      <div v-if="result" class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold mb-4">导入结果</h2>
        <div class="grid grid-cols-3 gap-4 text-center">
          <div>
            <div class="text-sm text-gray-500">总记录</div>
            <div class="text-2xl font-bold text-gray-900">{{ result.total_messages }}</div>
          </div>
          <div>
            <div class="text-sm text-gray-500">已导入</div>
            <div class="text-2xl font-bold text-green-600">{{ result.imported }}</div>
          </div>
          <div>
            <div class="text-sm text-gray-500">失败</div>
            <div class="text-2xl font-bold text-red-600">{{ result.failed }}</div>
          </div>
        </div>

        <div v-if="result.errors.length" class="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {{ result.errors[0].error_message }}
        </div>
      </div>

      <div v-if="errorMessage" class="rounded-md bg-red-50 p-4 text-sm text-red-700">
        {{ errorMessage }}
      </div>
    </div>
  </div>
</template>
