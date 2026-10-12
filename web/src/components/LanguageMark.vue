<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ family: string; label: string; color: string; small?: boolean }>()
const logoAssets: Record<string, string> = {
  fortran: '/language-marks/fortran.svg',
  cobol: '/language-marks/cobol.svg',
  c: '/language-marks/c.svg',
}
const logo = computed(() => logoAssets[props.family])
</script>

<template>
  <div class="language-mark" :class="[`language-mark--${family}`, { 'language-mark--small': small }]" :style="{ '--mark-color': color }" aria-hidden="true">
    <img v-if="logo" :src="logo" alt="" width="192" height="192" draggable="false" />
    <span v-else-if="family === 'lisp'" class="language-wordmark"><span class="lisp-parenthesis">(</span>LISP<span class="lisp-parenthesis">)</span></span>
    <span v-else class="language-wordmark">{{ label }}</span>
  </div>
</template>
