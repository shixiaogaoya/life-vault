<script setup lang="ts">
interface Filters {
  chat_id: string
  date_from: string
  date_to: string
}

const emit = defineEmits<{
  'filter-change': [filters: Filters]
}>()

const filters = ref<Filters>({
  chat_id: '',
  date_from: '',
  date_to: '',
})

watch(filters, (newFilters) => {
  emit('filter-change', newFilters)
}, { deep: true })
</script>

<template>
  <div class="filter-bar bg-white rounded-lg shadow p-4 mb-4">
    <div class="flex flex-wrap gap-4">
      <div class="flex-1 min-w-[200px]">
        <label class="block text-sm font-medium text-gray-700 mb-1">联系人</label>
        <input
          v-model="filters.chat_id"
          type="text"
          placeholder="输入联系人 ID"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
      </div>
      <div class="flex-1 min-w-[150px]">
        <label class="block text-sm font-medium text-gray-700 mb-1">开始日期</label>
        <input
          v-model="filters.date_from"
          type="date"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
      </div>
      <div class="flex-1 min-w-[150px]">
        <label class="block text-sm font-medium text-gray-700 mb-1">结束日期</label>
        <input
          v-model="filters.date_to"
          type="date"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
      </div>
    </div>
  </div>
</template>
