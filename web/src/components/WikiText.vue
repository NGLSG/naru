<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ text: string }>()
const tokens = computed(() => props.text.split(/(\[\[[^\]]+\]\]|`[^`]+`)/g).filter(Boolean).map(text => {
  if (text.startsWith('[[')) { const [family, label] = text.slice(2, -2).split('|'); return { kind: 'link', text: label ?? family, href: `#/language/${encodeURIComponent(family!)}` } }
  if (text.startsWith('`')) return { kind: 'code', text: text.slice(1, -1), href: '' }
  return { kind: 'text', text, href: '' }
}))
</script>
<template><template v-for="(token, index) in tokens" :key="index"><a v-if="token.kind === 'link'" :href="token.href">{{ token.text }}</a><code v-else-if="token.kind === 'code'">{{ token.text }}</code><template v-else>{{ token.text }}</template></template></template>
