<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import catalog from 'virtual:archive-catalog'
import wiki from 'virtual:archive-wiki'
import WikiArticle from './components/WikiArticle.vue'
import WikiIndex from './components/WikiIndex.vue'
import DialectLibrary from './components/DialectLibrary.vue'
import ContributionForm from './components/ContributionForm.vue'
import Icon from './components/Icon.vue'
import LanguageMark from './components/LanguageMark.vue'
import LanguageTrace from './components/LanguageTrace.vue'
import type { ArchiveEntry } from './types'

type Pane = 'index' | 'about' | 'contribute' | 'entry' | 'family' | 'dialects' | null
const pane = ref<Pane>(null)
const reading = ref<'index' | 'entry' | 'family' | 'dialects' | null>(null)
const familyId = ref('')
const contentHash = ref('')
const isModal = computed(() => pane.value === 'about' || pane.value === 'contribute')
const entryId = ref('')
const gallery = ref<HTMLElement>()
const dialog = ref<HTMLDialogElement>()
const showVersions = ref(false)
const progress = ref(0)
const activeIndex = ref(0)
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const featuredIds = new Set(['fortran/ii-1958', 'algol/60', 'cobol/60', 'lisp/1.5/1962', 'basic/1964', 'pli/1966', 'bcpl', 'simula/67', 'apl/360', 'pascal/1970', 'b/1972', 'c/kr/1978'])
const exhibits = computed(() => showVersions.value ? catalog.entries : catalog.entries.filter(entry => featuredIds.has(entry.id)))
const current = computed(() => exhibits.value[activeIndex.value] ?? exhibits.value[0])
const selectedEntry = computed(() => catalog.entries.find(entry => entry.id === entryId.value))
const collectionStart = catalog.entries[0]?.year
const collectionEnd = catalog.entries.at(-1)?.year
const eras = computed(() => {
  const first = exhibits.value[0]?.year
  const last = exhibits.value.at(-1)?.year
  if (first === undefined || last === undefined) return []
  const decades = []
  for (let year = Math.ceil(first / 10) * 10; year < last; year += 10) decades.push(year)
  return [...new Set([first, ...decades, last])]
})
const displayNumber = (number: number) => String(number).padStart(2, '0')

function route() {
  const hash = window.location.hash
  if (hash.startsWith('#/archive/')) {
    let id = ''
    try { id = decodeURIComponent(hash.slice(10)) } catch { /* malformed link falls back to index */ }
    entryId.value = id
    pane.value = catalog.entries.some(entry => entry.id === id) ? 'entry' : 'index'
  } else if (hash.startsWith('#/language/')) {
    try { familyId.value = decodeURIComponent(hash.slice(11)) } catch { familyId.value = '' }
    pane.value = wiki.families[familyId.value] ? 'family' : 'index'
  } else pane.value = ({ '#/index': 'index', '#/dialects': 'dialects', '#/about': 'about', '#/contribute': 'contribute' } as Record<string, Pane>)[hash] ?? null
  if (!isModal.value) { reading.value = pane.value as typeof reading.value; contentHash.value = hash }
}
function navigate(to: 'index' | 'about' | 'contribute') { window.location.hash = `/${to}` }
function openEntry(entry: ArchiveEntry) { window.location.hash = `/archive/${encodeURIComponent(entry.id)}` }
function closePane() {
  history.replaceState(null, '', window.location.pathname + window.location.search + (isModal.value ? contentHash.value : ''))
  route()
}
function goHome() { history.replaceState(null, '', window.location.pathname + window.location.search); route(); window.scrollTo({ top: 0 }) }
function skipToContent() { const element = reading.value ? document.getElementById('article-title') : gallery.value; element?.scrollIntoView({ block: 'start' }); element?.focus({ preventScroll: true }) }
function onDialogClick(event: MouseEvent) { if (event.target === dialog.value) closePane() }
watch([pane, entryId, familyId], async ([value], [previous]) => {
  await nextTick()
  if (isModal.value && dialog.value && !dialog.value.open) dialog.value.showModal()
  if (!isModal.value && dialog.value?.open) dialog.value.close()
  dialog.value?.querySelector('.pane-scroll')?.scrollTo({ top: 0 })
  if (isModal.value) dialog.value?.querySelector<HTMLElement>('#pane-title')?.focus({ preventScroll: true })
  else if (value && previous !== 'about' && previous !== 'contribute') { window.scrollTo({ top: 0, behavior: 'instant' }); document.getElementById('article-title')?.focus({ preventScroll: true }) }
  const title = value === 'entry' && selectedEntry.value ? `${selectedEntry.value.label} ${wiki.versions[selectedEntry.value.id]?.name ?? selectedEntry.value.year}`
    : value === 'family' ? `${wiki.families[familyId.value]?.name} · 语言总览` : value === 'dialects' ? '方言与规则库'
    : value === 'index' ? '馆藏索引' : value === 'about' ? '关于档案馆' : value === 'contribute' ? '共建档案' : '语言数字档案馆'
  document.title = `${title} · Naru`
})

let scrollFrame = 0
function syncScroll() {
  if (scrollFrame) return
  scrollFrame = requestAnimationFrame(() => {
    const element = gallery.value
    if (element) {
      const maximum = element.scrollWidth - element.clientWidth
      progress.value = maximum > 0 ? element.scrollLeft / maximum : 0
      const first = element.querySelector<HTMLElement>('.exhibit')
      if (first?.offsetWidth) activeIndex.value = Math.min(exhibits.value.length - 1, Math.max(0, Math.round(element.scrollLeft / first.offsetWidth)))
    }
    scrollFrame = 0
  })
}
function move(direction: number) {
  const element = gallery.value
  const card = element?.querySelector<HTMLElement>('.exhibit')
  if (!element || !card) return
  element.scrollBy({ left: direction * card.offsetWidth * (element.clientWidth > 800 ? 2 : 1), behavior: reducedMotion.matches ? 'instant' : 'smooth' })
}
function seek(value: number) {
  const element = gallery.value
  if (element) element.scrollTo({ left: value * (element.scrollWidth - element.clientWidth), behavior: 'instant' })
}
function jumpToYear(year: number) {
  const index = exhibits.value.findIndex(entry => entry.year >= year)
  const element = gallery.value
  const card = element?.querySelector<HTMLElement>('.exhibit')
  if (element && card) element.scrollTo({ left: Math.max(0, index < 0 ? exhibits.value.length - 1 : index) * card.offsetWidth, behavior: reducedMotion.matches ? 'instant' : 'smooth' })
}
function handleWheel(event: WheelEvent) {
  const element = gallery.value
  if (!element || event.ctrlKey || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return
  const delta = event.deltaY * (event.deltaMode === 1 ? 24 : event.deltaMode === 2 ? element.clientWidth : 1)
  if ((delta < 0 && element.scrollLeft <= 0) || (delta > 0 && element.scrollLeft >= element.scrollWidth - element.clientWidth - 1)) return
  event.preventDefault()
  element.scrollLeft += delta
}
function galleryKey(event: KeyboardEvent) {
  if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); move(event.key === 'ArrowRight' ? 1 : -1) }
  if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); seek(event.key === 'Home' ? 0 : 1) }
}
watch(showVersions, async () => { activeIndex.value = 0; progress.value = 0; await nextTick(); seek(0) })
let resizeObserver: ResizeObserver | undefined
onMounted(() => {
  route()
  window.addEventListener('hashchange', route)
  gallery.value?.addEventListener('wheel', handleWheel, { passive: false })
  resizeObserver = new ResizeObserver(syncScroll)
  if (gallery.value) resizeObserver.observe(gallery.value)
})
onBeforeUnmount(() => {
  window.removeEventListener('hashchange', route)
  gallery.value?.removeEventListener('wheel', handleWheel)
  resizeObserver?.disconnect()
  cancelAnimationFrame(scrollFrame)
})
</script>

<template>
  <a class="skip-link" :href="reading ? '#article-title' : '#timeline'" @click.prevent="skipToContent">跳至主要内容</a>
  <div class="archive-shell">
    <div class="archive-paper" aria-hidden="true"><span class="paper-margin">NARU ARCHIVE / {{ collectionStart }} — {{ collectionEnd }}</span><span class="paper-folio">001</span></div>
    <header class="site-header">
      <a class="brand" href="#" aria-label="Naru 语言数字档案馆首页" @click.prevent="goHome">
        <svg class="brand-mark" viewBox="0 0 40 40" fill="none" aria-hidden="true"><circle cx="20" cy="20" r="17.5" stroke="currentColor" /><ellipse cx="20" cy="20" rx="8.2" ry="17.5" stroke="currentColor" /><ellipse cx="20" cy="20" rx="17.5" ry="7.3" stroke="currentColor" /><path d="M2.5 20h35M20 2.5v35" stroke="currentColor" /></svg>
        <span class="brand-word">naru<span class="brand-period">.</span></span><span class="brand-subtitle">语言数字档案馆<span class="mono">LANGUAGE ARCHIVE</span></span>
      </a>
      <nav class="primary-nav" aria-label="主导航">
        <a href="#" :class="{ 'nav-active': !reading }" @click.prevent="goHome">时间线<span v-if="!reading" class="nav-dot" /></a>
        <a href="#/index" :class="{ 'nav-active': reading === 'index' || reading === 'entry' || reading === 'family' }" @click.prevent="navigate('index')">语言百科<span class="nav-count mono">{{ displayNumber(catalog.entries.length) }}</span></a>
        <a href="#/dialects">规则库</a>
        <a href="#/about" @click.prevent="navigate('about')">关于</a>
      </nav>
      <a href="#/contribute" class="contribute-link" @click.prevent="navigate('contribute')">留下你的记忆<Icon name="arrow-up-right" :size="16" /></a>
    </header>

    <main v-show="!reading">
      <section class="intro" aria-labelledby="home-title">
        <div class="intro-main">
          <p class="eyebrow"><span class="tiny-cross">+</span> AN OPEN MUSEUM OF PROGRAMMING LANGUAGES</p>
          <h1 id="home-title">那些语言，<span>仍在回响。</span></h1>
          <p class="intro-english">Every language leaves a trace.</p>
        </div>
        <div class="intro-aside"><span class="edition-label mono">VOL. 001 / AN ONGOING HISTORY</span><p>从一行旧代码，回到思想诞生的地方。<br />保存它的来处，也寻找它的下一次运行。</p><span class="intro-date mono">{{ collectionStart }} <span>—</span> {{ collectionEnd }} <span class="date-note">/ 馆藏年代</span></span></div>
      </section>

      <section id="timeline" class="timeline" aria-label="语言历史时间线">
        <div class="timeline-topline">
          <div class="timeline-heading"><span class="mono">01</span><h2>沿着时间，重新遇见</h2><span class="timeline-subheading mono">THE LANGUAGE CONTINUUM</span></div>
          <div class="view-switch" aria-label="时间线视角"><button :class="{ active: !showVersions }" :aria-pressed="!showVersions" @click="showVersions = false">语言足迹</button><span>/</span><button :class="{ active: showVersions }" :aria-pressed="showVersions" @click="showVersions = true">全部版本 <span class="mono">{{ catalog.entries.length }}</span></button></div>
        </div>
        <div ref="gallery" class="timeline-gallery" tabindex="0" aria-label="横向浏览时间线，可使用左右方向键" @scroll="syncScroll" @keydown="galleryKey">
          <div class="timeline-track">
            <article v-for="(entry, index) in exhibits" :key="entry.id" class="exhibit" :style="{ '--exhibit-color': entry.color }">
              <button class="exhibit-button" :aria-label="`打开 ${entry.label} ${entry.year}，${entry.variant}`" @click="openEntry(entry)">
                <div class="exhibit-object">
                  <LanguageTrace :entry="entry" />
                  <span class="exhibit-number mono">FIG. {{ displayNumber(index + 1) }}</span>
                  <span class="object-caption">{{ entry.keywords.slice(0, 2).join(' / ') }}</span>
                  <LanguageMark :family="entry.family" :label="entry.label" :color="entry.color" />
                  <span class="object-open"><Icon name="arrow-up-right" :size="20" /></span>
                </div>
                <div class="exhibit-axis"><span class="exhibit-tick" /><span class="exhibit-dot" /><span class="axis-minor" /></div>
                <div class="exhibit-label">
                  <span class="exhibit-year mono">{{ entry.year }}</span><h3>{{ entry.label }}</h3><p class="exhibit-variant">{{ entry.variant }}</p><p class="exhibit-caption">{{ entry.caption }}</p>
                  <div class="exhibit-foot"><span>{{ wiki.versions[entry.id]?.implementation ? '已关联方言实现' : `${wiki.families[entry.family]?.sections.length ?? 0} 节百科正文` }}</span><span class="exhibit-read">阅读词条<Icon name="arrow-right" :size="15" /></span></div>
                </div>
              </button>
            </article>
            <div class="timeline-end"><span class="end-cross">+</span><p>历史仍在书写。<br /><em>下一页，或许来自你。</em></p><a href="#/contribute" @click.prevent="navigate('contribute')">补充一份记忆<Icon name="arrow-up-right" :size="16" /></a></div>
          </div>
        </div>
        <div class="timeline-bottomline">
          <p class="browse-hint"><span class="hint-line" /><span>滚动，沿时间漫游</span><span class="mono">SCROLL TO EXPLORE</span></p>
          <div class="gallery-counter mono" aria-live="polite"><span>{{ displayNumber(activeIndex + 1) }}</span> / {{ displayNumber(exhibits.length) }}</div>
          <div class="gallery-controls"><button :disabled="progress <= .001" aria-label="向前浏览语言" @click="move(-1)"><Icon name="arrow-left" /></button><button :disabled="progress >= .999" aria-label="向后浏览语言" @click="move(1)"><Icon name="arrow-right" /></button></div>
        </div>
        <div class="chronology-navigation">
          <div class="chronology-label mono">CHRONOLOGY<span>{{ current?.year }} / {{ current?.label }}</span></div>
          <div class="chronology-scrubber"><input aria-label="时间线浏览位置" type="range" min="0" max="1000" :value="Math.round(progress * 1000)" :style="{ '--progress': `${progress * 100}%` }" @input="seek(Number(($event.target as HTMLInputElement).value) / 1000)" /><div class="era-labels"><button v-for="year in eras" :key="year" class="mono" :class="{ active: current?.year === year }" @click="jumpToYear(year)">{{ year }}</button></div></div>
        </div>
      </section>
    </main>
    <main v-if="reading === 'entry' && selectedEntry"><WikiArticle :entry="selectedEntry" :family="selectedEntry.family" @contribute="navigate('contribute')" /></main>
    <main v-else-if="reading === 'family'"><WikiArticle :family="familyId" @contribute="navigate('contribute')" /></main>
    <WikiIndex v-else-if="reading === 'index'" />
    <DialectLibrary v-else-if="reading === 'dialects'" />

    <footer class="site-footer"><p>记住来路，<span>让思想继续发生。</span></p><span class="footer-middle">{{ catalog.families.length }} 个语言谱系 · {{ catalog.entries.length }} 份档案条目 · 开放共建</span><a href="#/about" class="mono" @click.prevent="navigate('about')">PRESERVED WITH NARU <span>↗</span></a></footer>
  </div>

  <Teleport to="body">
    <dialog ref="dialog" class="archive-dialog" aria-labelledby="pane-title" @cancel.prevent="closePane" @click="onDialogClick">
      <div class="pane-scroll"><div class="pane-topbar"><span class="mono">NARU / OPEN ARCHIVE</span><button class="close-button" aria-label="关闭面板" @click="closePane"><Icon name="close" :size="22" /></button></div>
        <ContributionForm v-if="pane === 'contribute'" :entries="catalog.entries" :initial-language="selectedEntry && reading === 'entry' ? `${selectedEntry.label} ${selectedEntry.year} · ${selectedEntry.variant}` : reading === 'family' ? wiki.families[familyId]?.name : ''" />
        <section v-else-if="pane === 'about'" class="about-pane">
          <p class="eyebrow">ABOUT THE ARCHIVE / 关于档案馆</p><h2 id="pane-title" tabindex="-1">过去的语言，<br /><em>未来的可能。</em></h2>
          <span class="about-monogram" aria-hidden="true">n.</span>
          <p class="about-lead">一座可以继续生长的编程语言数字档案馆。</p><p>一本旧手册、一段程序、一位亲历者的记忆，都可能保存着一门语言独特的世界。Naru 想让这些思想重新被阅读，也逐步让旧程序在今天的机器上再次运行。</p>
          <div class="about-principles"><article><span class="mono">01 / PRESERVE</span><h3>保留来处</h3><p>原始资料、文献出处与版本差异一起存档。时间线的年份表示所选语言或版本，条目内另列文献年代。</p></article><article><span class="mono">02 / RECONSTRUCT</span><h3>逐步复原</h3><p>用开放的语言规则重建行为。每份条目保留实际复原记录；收藏文献，并不等于已经实现该语言。</p></article><article><span class="mono">03 / REMEMBER</span><h3>共同记忆</h3><p>尊重亲历者，也保留核对的过程。不同记忆和实现差异，可以成为后续考据的起点。</p></article></div>
          <p class="about-end">即使有一天，Naru 自己也成为历史，<br />愿这些思想，仍有下一位讲述者。</p><button class="text-link" @click="navigate('contribute')">留下你的记忆<Icon name="arrow-up-right" :size="17" /></button>
        </section>
      </div>
    </dialog>
  </Teleport>
</template>
