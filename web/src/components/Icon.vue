<script setup lang="ts">
withDefaults(defineProps<{ name: 'arrow-right' | 'arrow-left' | 'arrow-up-right' | 'close' | 'search' | 'file' | 'download' | 'check' | 'plus'; size?: number }>(), { size: 20 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-if="name === 'arrow-right'" d="M4 12h15m-6-6 6 6-6 6" />
    <path v-else-if="name === 'arrow-left'" d="M20 12H5m6-6-6 6 6 6" />
    <path v-else-if="name === 'arrow-up-right'" d="M6 18 18 6M6 6h12v12" />
    <path v-else-if="name === 'close'" d="m6 6 12 12M6 18 18 6" />
    <template v-else-if="name === 'search'"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></template>
    <template v-else-if="name === 'file'"><path d="M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6" /></template>
    <path v-else-if="name === 'download'" d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5" />
    <path v-else-if="name === 'check'" d="m5 12 4 4L19 6" />
    <path v-else-if="name === 'plus'" d="M12 5v14M5 12h14" />
  </svg>
</template>
