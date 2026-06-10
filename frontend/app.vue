<template>
  <div class="min-h-screen bg-gray-50">
    <nav class="border-b border-gray-200 bg-white">
      <div class="mx-auto flex max-w-4xl items-center justify-between px-6 py-3">
        <NuxtLink to="/" class="text-lg font-bold text-gray-900">LifeVault</NuxtLink>
        <div class="flex items-center gap-4 text-sm">
          <NuxtLink to="/" class="text-gray-600 hover:text-blue-600">消息</NuxtLink>
          <NuxtLink to="/search" class="text-gray-600 hover:text-blue-600">搜索</NuxtLink>
          <NuxtLink to="/import" class="text-gray-600 hover:text-blue-600">导入</NuxtLink>
          <NuxtLink to="/export" class="text-gray-600 hover:text-blue-600">导出</NuxtLink>
        </div>
      </div>
    </nav>
    <NuxtPage />
  </div>
</template>
