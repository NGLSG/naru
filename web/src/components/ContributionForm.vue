<script setup lang="ts">
import { ref } from 'vue'
import type { ArchiveEntry } from '../types'
import Icon from './Icon.vue'
const props = defineProps<{ entries: ArchiveEntry[]; initialLanguage?: string }>()
const language = ref(props.initialLanguage ?? '')
const name = ref('')
const kind = ref('亲历者记忆')
const memory = ref('')
const source = ref('')
const prepared = ref(false)
function prepare() {
  const draft = `# 语言档案补遗\n\n- 相关语言或版本: ${language.value}\n- 提供者: ${name.value || '未署名'}\n- 记录类型: ${kind.value}\n- 整理日期: ${new Date().toISOString().slice(0, 10)}\n- 来源或可核对线索: ${source.value || '待补充'}\n\n## 记忆与材料\n\n${memory.value}\n\n## 核对记录\n\n待社区核对；本稿尚未提交、未进入馆藏。\n`
  const url = URL.createObjectURL(new Blob([draft], { type: 'text/markdown;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'naru-archive-contribution.md'
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  prepared.value = true
}
</script>

<template>
  <section class="contribution">
    <p class="eyebrow">A LIVING ARCHIVE / 共建一份记忆</p>
    <h2 id="pane-title" tabindex="-1">你记得的，<br /><em>也值得被留下。</em></h2>
    <p class="pane-intro">一段亲历、一本旧手册，或一个被遗忘的实现细节。先整理成补遗草稿，为未来的考据留下线索。</p>
    <form @submit.prevent="prepare">
      <div class="form-row"><label>语言 / 版本<input v-model="language" list="language-options" placeholder="例如：K&R C，1984" required maxlength="160" /><datalist id="language-options"><option v-for="entry in entries" :key="entry.id" :value="`${entry.label} ${entry.year}`" /></datalist></label><label>你的署名 <span>可选</span><input v-model="name" placeholder="如何称呼你" maxlength="100" /></label></div>
      <label>材料性质<select v-model="kind"><option>亲历者记忆</option><option>文献补充</option><option>条目勘误</option><option>复原建议</option></select></label>
      <label>你想留下什么<textarea v-model="memory" rows="5" placeholder="当时的机器、编译器版本、使用方式，以及你还记得的细节……" required maxlength="20000" /></label>
      <label>文献出处 / 可核对的线索 <span>可选</span><input v-model="source" placeholder="书名、页码、链接，或其他见证者" maxlength="2000" /></label>
      <div class="form-footer"><p>草稿保存在你的电脑上。<br />社区提交与审核服务尚未接入。</p><button class="solid-button" type="submit"><Icon :name="prepared ? 'check' : 'download'" :size="17" />{{ prepared ? '再次下载草稿' : '整理并下载草稿' }}</button></div>
      <p v-if="prepared" class="form-success" role="status">补遗草稿已生成。原始回忆和待核对信息会一起保留。</p>
    </form>
  </section>
</template>
