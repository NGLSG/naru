<script setup lang="ts">
import { computed, ref } from 'vue'
import wiki from 'virtual:archive-wiki'
import Icon from './Icon.vue'
const query = ref('')
const category = ref('all')
const categories = [...new Set(wiki.modules.map(item => item.category))]
const modules = computed(() => wiki.modules.filter(item => (category.value === 'all' || item.category === category.value) && `${item.name} ${item.description} ${item.imports.join(' ')}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const entryFor: Record<string, string> = { b: 'b/1972', pascal: 'pascal/iso-1983', c11: 'c/11' }
</script>
<template>
  <main class="dialect-library">
    <div class="wiki-breadcrumb"><a href="#/index">语言百科</a><span>/</span><span>方言与规则库</span><span class="wiki-breadcrumb-end mono">THE RULE COLLECTION</span></div>
    <header class="dialect-intro"><div><p class="eyebrow">IMPLEMENTATION / 实现档案</p><h1 id="article-title" tabindex="-1">语言如何被重新构造<span>。</span></h1><p>从独立语言的前端，到可组合的基础设施。<br />这里直接读取工作区的 <code>dialects/</code>，保留实际模块、导入关系与源码。</p></div><div class="dialect-count mono">{{ wiki.modules.length }}<span>RULE FILES</span></div></header>
    <div class="dialect-language-entries"><a v-for="implementation in wiki.implementations" :key="implementation.module" :href="`#/archive/${encodeURIComponent(entryFor[implementation.module]!)}`"><span class="eyebrow">LANGUAGE FRONTEND</span><h2>{{ implementation.name }}</h2><p>{{ implementation.status }}</p><code>{{ implementation.frontend }}</code><Icon name="arrow-up-right" :size="20" /></a></div>
    <div class="dialect-browser"><aside><span class="eyebrow">RULE GROUPS</span><button :class="{ active: category === 'all' }" @click="category = 'all'">全部模块 <span>{{ wiki.modules.length }}</span></button><button v-for="group in categories" :key="group" :class="{ active: category === group }" @click="category = group">{{ group }}<span>{{ wiki.modules.filter(item => item.category === group).length }}</span></button></aside><section><div class="dialect-search"><Icon name="search" :size="18" /><input v-model="query" type="search" aria-label="搜索规则模块" placeholder="查找模块、能力或导入关系…" /><span class="mono">{{ modules.length }} RESULTS</span></div><p class="dialect-reading-note">声明数量用于了解源码规模，不表示语言覆盖率。共同导入模块，也不表示不同表面语言自动互操作。</p><details v-for="module in modules" :key="module.path" class="dialect-module"><summary><span class="mono module-name">{{ module.name }}</span><span>{{ module.description }}</span><small class="mono">{{ module.syntaxCount }} S / {{ module.effectCount }} E</small><Icon name="plus" :size="15" /></summary><div class="dialect-module-body"><p class="module-path mono">{{ module.path }}</p><dl><div><dt>规则声明</dt><dd>{{ module.syntaxCount }} syntax · {{ module.effectCount }} effect</dd></div><div><dt>直接导入</dt><dd>{{ module.imports.length ? module.imports.join(' · ') : '无直接导入' }}</dd></div><div v-if="module.frontends.length"><dt>前端关系</dt><dd>{{ module.frontends.join(' · ') }}</dd></div></dl><div class="module-source-row"><a :href="module.url" target="_blank" rel="noopener">阅读实际规则源码<Icon name="arrow-up-right" :size="14" /></a><code title="源码快照 SHA-256">SHA256 {{ module.sha256.slice(0, 12) }}</code></div></div></details><p v-if="!modules.length" class="dialect-empty">没有匹配的模块。<button @click="query = ''; category = 'all'">清除筛选</button></p></section></div>
    <aside class="dialect-composition-note"><span class="eyebrow">COMPOSITION</span><h2>一种语言，通常不止一个规则文件。</h2><p>C11 入口导入词法、预处理、语法、语义、布局和初始化等模块；B 与 Pascal 也复用了基础类型和管线。模块提供共同工具，语言版本仍由自身规则定义。组合入口同样列在这里，便于追踪它实际选用了什么。</p></aside>
  </main>
</template>
