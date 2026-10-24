<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import catalog from 'virtual:archive-catalog'
import wiki from 'virtual:archive-wiki'
import type { ArchiveEntry, WikiReference } from '../types'
import Icon from './Icon.vue'
import LanguageMark from './LanguageMark.vue'
import WikiText from './WikiText.vue'

const props = defineProps<{ family: string; entry?: ArchiveEntry }>()
defineEmits<{ contribute: [] }>()
const article = computed(() => wiki.families[props.family]!)
const version = computed(() => props.entry ? wiki.versions[props.entry.id] : undefined)
const editions = computed(() => catalog.entries.filter(entry => entry.family === props.family))
const display = computed(() => props.entry ?? editions.value[0]!)
const sections = computed(() => [...(version.value?.sections ?? []), ...article.value.sections])
const implementation = computed(() => version.value?.implementation ? wiki.implementations[version.value.implementation] : !props.entry ? Object.values(wiki.implementations).find(item => item.module === props.family || props.family === 'c' && item.module === 'c11') : undefined)
const modules = computed(() => wiki.modules.filter(item => implementation.value?.modules.includes(item.name) && !item.path.endsWith('-nobranch.stx')))
const references = computed(() => article.value.references.map((reference, index) => ({ ...reference, number: index + 1, href: sourceUrl(reference) })))
const documents = computed(() => (props.entry ? [props.entry] : editions.value).flatMap(entry => entry.documents))
const activeSection = ref('overview')
const copied = ref('')
const exampleIndex = ref(0)
const example = computed(() => implementation.value?.examples[exampleIndex.value])
const toc = computed(() => [{ id: 'overview', title: '概述' }, ...sections.value.map(section => ({ id: section.id, title: section.title })), { id: 'versions', title: '版本与方言' }, { id: 'reconstruction', title: 'Naru 复原记录' }, { id: 'references', title: '参考文献' }])
let observer: IntersectionObserver | undefined
function sourceUrl(reference: WikiReference) {
  if (reference.url) return reference.url
  for (const entry of catalog.entries) for (const doc of entry.documents) if (`${entry.id}/${doc.name}` === reference.file) return doc.url
  for (const entry of catalog.entries) if (reference.file?.startsWith(`${entry.id}/`)) return entry.indexUrl
  return ''
}
function jump(id: string) {
  activeSection.value = id
  document.getElementById(`wiki-${id}`)?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })
}
function cite(key: string) { return references.value.find(ref => ref.key === key) }
async function copy(text: string, label: string) { try { await navigator.clipboard.writeText(text); copied.value = label } catch { copied.value = '复制失败，请手动选择' } }
function share() { void copy(window.location.href, '链接已复制') }
function observeSections() {
  observer?.disconnect()
  observer = new IntersectionObserver(entries => {
    const visible = entries.filter(item => item.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
    if (visible[0]?.target.id) activeSection.value = visible[0].target.id.replace('wiki-', '')
  }, { rootMargin: '-12% 0px -65% 0px', threshold: 0 })
  document.querySelectorAll('.wiki-article [data-wiki-section]').forEach(element => observer?.observe(element))
}
watch(() => [props.family, props.entry?.id], () => { activeSection.value = 'overview'; exampleIndex.value = 0; copied.value = '' }, { flush: 'post' })
watch(sections, observeSections, { flush: 'post' })
onMounted(observeSections)
onBeforeUnmount(() => observer?.disconnect())
const day = (date: string) => new Date(date).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
</script>

<template>
  <div class="wiki-page" :style="{ '--language-color': display.color }">
    <div class="wiki-breadcrumb"><a href="#/index">语言百科</a><span>/</span><a :href="`#/language/${family}`">{{ article.name }}</a><template v-if="entry"><span>/</span><span>{{ version?.name }}</span></template><span class="wiki-breadcrumb-end mono">NARU / ENCYCLOPEDIA</span></div>
    <div class="wiki-toolbar"><div><a :href="`#/language/${family}`" :class="{ active: !entry }">语言总览</a><a v-if="entry" :href="`#/archive/${encodeURIComponent(entry.id)}`" class="active">版本条目</a><button @click="jump('reconstruction')">复原记录</button></div><div><a href="#/contribute">补充 / 勘误<Icon name="plus" :size="13" /></a><button @click="share"><Icon name="arrow-up-right" :size="13" />分享</button></div></div>
    <div class="wiki-layout">
      <aside class="wiki-toc"><div class="wiki-toc-inner"><span class="eyebrow">ON THIS PAGE</span><h2>本页目录</h2><nav aria-label="词条目录"><button v-for="(item, index) in toc" :key="item.id" :class="{ active: activeSection === item.id }" @click="jump(item.id)"><span class="mono">{{ String(index).padStart(2, '0') }}</span>{{ item.title }}</button></nav><a href="#/dialects" class="wiki-toc-foot">浏览规则库<Icon name="arrow-up-right" :size="14" /></a><button class="wiki-back-top" @click="jump('overview')">↑ 回到开篇</button></div></aside>
      <article class="wiki-article">
        <header id="wiki-overview" data-wiki-section class="wiki-heading">
          <p class="eyebrow">{{ entry ? 'VERSION ENTRY / 版本条目' : 'LANGUAGE FAMILY / 语言谱系' }}<span class="wiki-entry-number mono">{{ entry ? entry.year : display.year }} —</span></p>
          <h1 id="article-title" tabindex="-1">{{ article.name }}<span v-if="entry" class="wiki-title-year">{{ entry.year }}</span></h1>
          <p class="wiki-subtitle">{{ entry ? version?.name : article.fullName }}</p>
          <p class="wiki-motto">{{ article.subtitle }}</p>
          <p class="wiki-lead"><WikiText :text="version?.lead ?? article.lead" /></p>
          <p v-if="entry" class="wiki-family-context">本页属于 <a :href="`#/language/${family}`">{{ article.name }} 语言谱系</a>，另有 {{ editions.length - 1 }} 个版本档案可供对照。</p>
          <div v-if="version" class="wiki-version-focus"><span>本版线索</span><span v-for="feature in version.features" :key="feature">{{ feature }}</span></div>
          <details class="wiki-mobile-record"><summary>语言基本资料<span>{{ article.origin }}</span></summary><dl><div><dt>人物 / 机构</dt><dd>{{ article.people }}</dd></div><div><dt>计算模型</dt><dd>{{ article.model }}</dd></div><div><dt>历史环境</dt><dd>{{ article.setting }}</dd></div><div v-if="entry"><dt>原件年代</dt><dd>{{ entry.yearLabel }}</dd></div></dl></details>
          <div class="wiki-edition-strip"><span>阅读版本</span><a :href="`#/language/${family}`" :class="{ selected: !entry }">总览</a><a v-for="edition in editions" :key="edition.id" :href="`#/archive/${encodeURIComponent(edition.id)}`" :class="{ selected: edition.id === entry?.id }">{{ edition.year }}<small v-if="editions.filter(item => item.year === edition.year).length > 1"> {{ wiki.versions[edition.id]?.name }}</small></a></div>
        </header>
        <section v-for="(section, sectionIndex) in sections" :id="`wiki-${section.id}`" :key="section.id" class="wiki-section" data-wiki-section>
          <div class="wiki-section-heading"><span class="mono">{{ String(sectionIndex + 1).padStart(2, '0') }}</span><h2>{{ section.title }}</h2><button aria-label="补充或修正本节" @click="$emit('contribute')">补充<Icon name="plus" :size="12" /></button></div>
          <template v-for="(block, blockIndex) in section.blocks" :key="blockIndex">
            <p v-if="block.kind === 'paragraph'"><WikiText :text="block.text" /></p>
            <figure v-else-if="block.kind === 'code'" class="wiki-code"><figcaption><strong>{{ block.title }}</strong><span class="mono">{{ block.language }}</span></figcaption><pre><code><span v-for="(line, index) in block.code.split('\n')" :key="index" class="code-line"><i aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</i><span>{{ line || ' ' }}</span></span></code></pre><ol class="code-annotations"><li v-for="line in block.notes" :key="line"><WikiText :text="line" /></li></ol></figure>
            <div v-else-if="block.kind === 'table'" class="wiki-table-scroll" tabindex="0" aria-label="可横向滚动的数据表"><table class="wiki-table"><thead><tr><th v-for="column in block.columns" :key="column" scope="col">{{ column }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in block.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex"><WikiText :text="cell" /></td></tr></tbody></table></div>
            <aside v-else-if="block.kind === 'note'" class="wiki-note"><span class="mono">ARCHIVE NOTE</span><strong>{{ block.title }}</strong><p><WikiText :text="block.text" /></p></aside>
          </template>
          <p class="wiki-section-sources">本节依据 <template v-for="key in section.refs" :key="key"><button v-if="cite(key)" @click="jump(`ref-${cite(key)!.number}`)">[{{ cite(key)!.number }}]</button></template></p>
        </section>

        <section id="wiki-versions" class="wiki-section" data-wiki-section>
          <div class="wiki-section-heading"><span class="mono">V</span><h2>版本与方言</h2></div>
          <p>同一谱系中的文献与实现分别立档。选中一个版本，可以阅读它的历史边界与实际复原状态。</p>
          <div class="wiki-version-list"><a v-for="edition in editions" :key="edition.id" :href="`#/archive/${encodeURIComponent(edition.id)}`" :class="{ selected: entry?.id === edition.id }"><span class="version-year mono">{{ edition.year }}</span><div><h3>{{ wiki.versions[edition.id]?.name ?? edition.variant }}</h3><p>{{ wiki.versions[edition.id]?.focus }}</p><small>{{ wiki.versions[edition.id]?.boundary }}</small></div><span class="version-state">{{ wiki.versions[edition.id]?.implementation ? '有规则实现' : '文献档案' }}<Icon name="arrow-up-right" :size="16" /></span></a></div>
        </section>

        <section id="wiki-reconstruction" class="wiki-section" data-wiki-section>
          <div class="wiki-section-heading"><span class="mono">R</span><h2>Naru 复原记录</h2></div>
          <template v-if="implementation">
            <div class="implementation-heading"><span class="implementation-dot" /><strong>{{ implementation.status }}</strong><code>{{ implementation.frontend }}</code></div>
            <p>{{ implementation.summary }}</p>
            <div class="implementation-scope"><div><h3>当前规则包含</h3><ul><li v-for="feature in implementation.features" :key="feature">{{ feature }}</li></ul></div><div><h3>尚需核对与补齐</h3><ul><li v-for="limit in implementation.limits" :key="limit">{{ limit }}</li></ul></div></div>
            <div v-if="implementation.module === 'c11' && wiki.report" class="wiki-test-record"><div><span class="eyebrow">SAVED TEST RECORD</span><strong class="mono">{{ wiki.report.passed }}<small>/ {{ wiki.report.total }}</small></strong></div><p>仓库保存的压力测试<br /><span>{{ day(wiki.report.recordedAt) }} · 非本次重跑</span></p><a :href="wiki.report.url" target="_blank" rel="noopener">查看原始报告<Icon name="arrow-up-right" :size="14" /></a><div class="test-case-list"><span v-for="item in wiki.report.cases" :key="item.name">{{ item.passed ? '✓' : '×' }} {{ item.name }}</span></div></div>
            <h3 class="wiki-subheading">来自仓库的程序</h3>
            <div class="source-example-tabs"><button v-for="(item, index) in implementation.examples" :key="item.path" :class="{ active: index === exampleIndex }" @click="exampleIndex = index">{{ item.path.split('/').at(-1) }}</button></div>
            <figure v-if="example" class="wiki-code source-code"><figcaption><a :href="example.url" target="_blank" rel="noopener">{{ example.path }}<Icon name="arrow-up-right" :size="12" /></a><button @click="copy(example.code, '代码已复制')">复制代码</button></figcaption><pre><code>{{ example.code.trim() }}</code></pre></figure>
            <details class="wiki-evidence"><summary>查看构建命令与规则组成 <span class="mono">{{ modules.length }} MODULES</span></summary><p>命令供本地项目使用。页面展示现有源文件与记录，没有在线执行编译。</p><pre>{{ implementation.command }}</pre><button class="text-link" @click="copy(implementation.command, '命令已复制')">复制命令<Icon name="arrow-right" :size="14" /></button><div class="rule-dependency-list"><a v-for="module in modules" :key="module.path" :href="module.url" target="_blank" rel="noopener"><span>{{ module.name }}</span><small>{{ module.description }}</small><Icon name="arrow-up-right" :size="12" /></a></div><div class="wiki-evidence-links"><a v-for="file in implementation.files" :key="file.path" :href="file.url" target="_blank" rel="noopener">{{ file.path }} ↗</a></div></details>
          </template>
          <template v-else><p>{{ version ? version.boundary : '本谱系已有文献档案，尚未发现对应的独立语言方言入口。' }}</p><p>通用基础规则为后续复原提供工具。具体版本的词法、语义、运行时与验收，需要按原始资料逐项建立。</p><a class="wiki-inline-action" href="#/dialects">查看现有可组合规则<Icon name="arrow-right" :size="16" /></a><p v-if="family === 'c' || family === 'pascal'" class="wiki-implementation-crosslink">本谱系另有规则实现：<a :href="`#/archive/${encodeURIComponent(family === 'c' ? 'c/11' : 'pascal/iso-1983')}`">{{ family === 'c' ? 'C11' : 'ISO 7185 Pascal 目标子集' }}</a>。</p></template>
        </section>

        <section id="wiki-references" class="wiki-section wiki-references" data-wiki-section>
          <div class="wiki-section-heading"><span class="mono">S</span><h2>参考文献与考据</h2></div>
          <p class="references-intro">正文由档案馆整理撰写，文献用于核对与追溯。源程序节选和自编示例分别标注；原始资料保留各自的版本与身份。</p>
          <ol><li v-for="reference in references" :id="`wiki-ref-${reference.number}`" :key="reference.key"><span class="mono">{{ reference.number.toString().padStart(2, '0') }}</span><div><a v-if="reference.href" :href="reference.href" target="_blank" rel="noopener">{{ reference.title }}<Icon name="arrow-up-right" :size="12" /></a><span v-else>{{ reference.title }}</span><p>{{ reference.locator }} {{ reference.unavailable ?? '' }}</p></div></li></ol>
          <details class="wiki-evidence"><summary>馆藏原件与原始条目卡 <span class="mono">{{ documents.length }} FILES</span></summary><div class="wiki-document-list"><a v-for="doc in documents" :key="doc.url" :href="doc.url" :download="doc.name"><Icon name="file" :size="16" /><span>{{ doc.name }}</span><small class="mono">{{ doc.format }}</small><Icon name="download" :size="13" /></a></div><p v-if="!documents.length">{{ catalog.originalsWithheld ? '源码预览未附带史料原件，文献来源见条目卡。' : '本条目目前只有文献引用卡，未收藏原件。' }}</p><a v-for="edition in (entry ? [entry] : editions)" :key="edition.id" :href="edition.indexUrl" target="_blank" rel="noopener" class="original-index-link">原始记录：{{ edition.id }} ↗</a><p>原始卡片保留采集时状态；现行复原记录以本页关联的规则文件为依据。</p></details>
        </section>
        <section class="wiki-related"><span class="eyebrow">CONTINUE READING</span><h2>沿着这些线索，继续阅读</h2><div><a v-for="related in article.related" :key="related" :href="`#/language/${related}`"><span>{{ wiki.families[related]?.name }}</span><small>{{ wiki.families[related]?.subtitle }}</small><Icon name="arrow-right" :size="18" /></a></div></section>
        <footer class="wiki-article-footer"><span>本馆撰稿 · {{ day(wiki.editedAt) }}</span><a href="#/contribute">提供史料或修正这个条目 ↗</a></footer>
      </article>
      <aside class="wiki-infobox"><div class="wiki-infobox-inner"><span class="eyebrow">LANGUAGE RECORD</span><LanguageMark :family="family" :label="article.name" :color="display.color" /><h2>{{ article.name }}</h2><p class="infobox-fullname">{{ article.fullName }}</p><dl><div><dt>起点 / 谱系</dt><dd>{{ article.origin }}</dd></div><div><dt>人物 / 机构</dt><dd>{{ article.people }}</dd></div><div><dt>计算模型</dt><dd>{{ article.model }}</dd></div><div><dt>历史环境</dt><dd>{{ article.setting }}</dd></div><div v-if="entry"><dt>所选档案</dt><dd>{{ entry.variant }}</dd></div><div v-if="entry"><dt>原件年代</dt><dd>{{ entry.yearLabel }}</dd></div></dl><div class="infobox-implementation"><span class="implementation-dot" :class="{ pending: !implementation }" />{{ implementation ? '已关联规则源码' : '文献考据阶段' }}</div><a v-if="implementation" href="#/dialects" class="infobox-rule-link">{{ implementation.module }}<Icon name="arrow-up-right" :size="13" /></a><p class="infobox-footnote">{{ editions.length }} 个档案版本 · {{ editions.reduce((sum, item) => sum + item.documents.length, 0) }} 份原件</p></div></aside>
    </div>
    <div v-if="copied" class="wiki-copy-status" role="status"><Icon name="check" :size="14" />{{ copied }}<button aria-label="关闭提示" @click="copied = ''">×</button></div>
  </div>
</template>
