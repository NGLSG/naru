<script setup lang="ts">
import { computed, ref } from 'vue'
import catalog from 'virtual:archive-catalog'
import wiki from 'virtual:archive-wiki'
import Icon from './Icon.vue'
const query = ref('')
const implementedOnly = ref(false)
const entries = (family: string) => catalog.entries.filter(entry => entry.family === family)
const hasImplementation = (family: string) => entries(family).some(entry => wiki.versions[entry.id]?.implementation)
const results = computed(() => Object.entries(wiki.families).filter(([family, article]) => {
  if (implementedOnly.value && !hasImplementation(family)) return false
  const haystack = [article.name, article.fullName, article.people, article.model, article.lead, ...article.sections.flatMap(section => [section.title, ...section.blocks.map(block => 'text' in block ? block.text : '')]), ...entries(family).flatMap(entry => [entry.year, entry.variant, wiki.versions[entry.id]?.focus])].join(' ').toLowerCase()
  return query.value.trim().toLowerCase().split(/\s+/).every(term => haystack.includes(term))
}))
</script>
<template>
  <main class="wiki-index-page"><div class="wiki-breadcrumb"><a href="#">时间线</a><span>/</span><span>语言百科</span><span class="wiki-breadcrumb-end mono">THE ENCYCLOPEDIA</span></div><header class="wiki-index-heading"><div><p class="eyebrow">THE COLLECTION / 语言百科</p><h1 id="article-title" tabindex="-1">每一门语言，<br /><em>都有不止一段历史。</em></h1></div><p>{{ catalog.families.length }} 个谱系 · {{ catalog.entries.length }} 个版本档案<br /><span>从历史背景、语法与行为，读到实际的规则实现。</span></p></header><div class="wiki-index-search"><div><Icon name="search" :size="19" /><input v-model="query" type="search" aria-label="搜索语言百科正文和版本" placeholder="搜索语言、版本、人物，或一种语言特性…" /></div><label><input v-model="implementedOnly" type="checkbox" />已有关联实现</label><a href="#/dialects">方言与规则库<Icon name="arrow-up-right" :size="16" /></a></div><p class="wiki-index-count mono">{{ results.length }} LANGUAGE FAMILIES</p><div class="wiki-family-index"><article v-for="([family, article], index) in results" :key="family"><span class="mono index-row-number">{{ String(index + 1).padStart(2, '0') }}</span><a :href="`#/language/${family}`" class="index-family-name"><h2>{{ article.name }}</h2><span>{{ article.fullName }}</span></a><div class="index-family-body"><p>{{ article.subtitle }}</p><span>{{ article.model }}</span><div class="index-editions"><a v-for="entry in entries(family)" :key="entry.id" :href="`#/archive/${encodeURIComponent(entry.id)}`"><span class="mono">{{ entry.year }}</span>{{ wiki.versions[entry.id]?.name }}<i v-if="wiki.versions[entry.id]?.implementation" title="已关联规则实现" /></a></div></div><a :href="`#/language/${family}`" class="index-read-link" :aria-label="`阅读 ${article.name} 总览`"><Icon name="arrow-up-right" :size="21" /></a></article></div><p v-if="!results.length" class="dialect-empty">没有找到这条线索。<button @click="query = ''; implementedOnly = false">清除筛选</button></p><aside class="wiki-index-end"><span class="eyebrow">A LIVING COLLECTION</span><p>历史不只有一种讲述。<br /><span>你的材料和记忆，可以让这些条目更完整。</span></p><a href="#/contribute">补充一条线索<Icon name="plus" :size="16" /></a></aside></main>
</template>
