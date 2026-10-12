import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { readWiki } from './wiki.mjs'
import { readCatalog } from './catalog.mjs'

test('all archived versions have authored content and resolvable citations', async () => {
  const { catalog: wiki, available } = await readWiki()
  const archive = await readCatalog()
  const originals = new Set(archive.entries.flatMap(entry => entry.documents.map(doc => `${entry.id}/${doc.name}`)))
  for (const entry of archive.entries) {
    const article = wiki.families[entry.family]
    const version = wiki.versions[entry.id]
    assert.ok(article && version, `Missing authored entry: ${entry.id}`)
    assert.ok(version.lead.length > 30 && article.sections.length >= 3, entry.id)
    if (version.implementation) assert.ok(wiki.implementations[version.implementation], entry.id)
    const ids = [...version.sections, ...article.sections].map(section => section.id)
    assert.equal(new Set(ids).size, ids.length, `Duplicate anchors: ${entry.id}`)
    for (const section of [...version.sections, ...article.sections]) for (const key of section.refs) assert.ok(article.references.some(ref => ref.key === key), `Unresolved citation ${entry.id}/${key}`)
    for (const ref of article.references) {
      if (ref.file) assert.ok(originals.has(ref.file), `Missing original: ${ref.file}`)
      else if (ref.url.startsWith('/implementation/')) assert.ok(available.has(ref.url), `Missing rule evidence: ${ref.url}`)
      else assert.ok(ref.url.startsWith('https://'), ref.url)
    }
    for (const related of article.related) assert.ok(wiki.families[related], related)
  }
  assert.equal(wiki.versions['basic/1964'].implementation, undefined)
  assert.equal(wiki.versions['c/kr/1978'].implementation, undefined)
  assert.equal(wiki.versions['c/11'].implementation, 'c11')
  assert.ok(originals.has('c/89/rationale/title.html'))
})

test('rule snapshots and language compositions match real files', async () => {
  const { catalog: wiki, available } = await readWiki()
  for (const module of wiki.modules) {
    const bytes = await readFile(available.get(module.url), 'utf8')
    assert.equal(module.sha256, createHash('sha256').update(bytes).digest('hex'), module.path)
    for (const imported of module.imports) assert.ok(wiki.modules.some(candidate => candidate.name === imported), `Unresolved import ${module.name}/${imported}`)
  }
  for (const implementation of Object.values(wiki.implementations)) {
    const root = wiki.modules.find(module => module.name === implementation.module)
    assert.ok(root.frontends.includes(implementation.frontend))
    assert.ok(implementation.modules.includes(implementation.module))
    for (const name of implementation.modules) assert.ok(wiki.modules.some(module => module.name === name), name)
    for (const example of implementation.examples) assert.equal(example.code, await readFile(available.get(example.url), 'utf8'))
  }
  assert.ok(wiki.implementations.c11.modules.includes('c11.declarators'))
})

test('every encyclopedia view renders article text and navigation', async () => {
  const { createServer } = await import('vite')
  const { createSSRApp } = await import('vue')
  const { renderToString } = await import('vue/server-renderer')
  const server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  try {
    const { default: Article } = await server.ssrLoadModule('/src/components/WikiArticle.vue')
    const { default: Index } = await server.ssrLoadModule('/src/components/WikiIndex.vue')
    const { default: Rules } = await server.ssrLoadModule('/src/components/DialectLibrary.vue')
    const archive = await readCatalog()
    for (const entry of archive.entries) {
      const html = await renderToString(createSSRApp(Article, { family: entry.family, entry }))
      assert.ok(html.includes('id="article-title"'), entry.id)
      assert.ok(html.includes('id="wiki-references"') && html.includes('id="wiki-versions"'), entry.id)
      assert.ok(html.includes(`#/archive/${encodeURIComponent(entry.id)}`), entry.id)
      assert.ok(!html.includes('undefined') && !html.includes('NaN'), entry.id)
    }
    for (const family of archive.families) {
      const html = await renderToString(createSSRApp(Article, { family }))
      assert.ok(html.includes('LANGUAGE FAMILY'), family)
    }
    assert.ok((await renderToString(createSSRApp(Index))).includes('wiki-family-index'))
    assert.ok((await renderToString(createSSRApp(Rules))).includes('c11.frontend'))
  } finally { await server.close() }
})
