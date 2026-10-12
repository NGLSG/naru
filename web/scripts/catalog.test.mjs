import test from 'node:test'
import assert from 'node:assert/strict'
import { readCatalog, field } from './catalog.mjs'
import { access } from 'node:fs/promises'
import path from 'node:path'
import { historicalRoot } from './catalog.mjs'

test('multi-line original metadata is retained without merging other fields', () => {
  assert.equal(field('- 考据对象: first\n  second\n- 年份: 1978', '考据对象'), 'first second')
})

test('every existing archive entry is linked to its real documents and source card', async () => {
  const catalog = await readCatalog()
  assert.ok(catalog.entries.length >= 22)
  assert.equal(new Set(catalog.entries.map(entry => entry.id)).size, catalog.entries.length)
  for (const [index, entry] of catalog.entries.entries()) {
    assert.ok(entry.title && entry.subject && entry.author, entry.id)
    assert.ok(entry.year >= 1950 && entry.year <= 2026, entry.id)
    if (index) assert.ok(entry.year >= catalog.entries[index - 1].year)
    for (const document of entry.documents) {
      await access(path.join(historicalRoot, entry.id, document.name))
      assert.ok(document.bytes > 0)
      assert.ok(document.url.startsWith(`/archive/${entry.id}/`))
    }
  }
  assert.equal(catalog.entries.find(entry => entry.id === 'c/kr/1978').year, 1978)
  assert.equal(catalog.entries.find(entry => entry.id === 'fortran/66').documents.length, 0)
  assert.equal(catalog.documentCount, catalog.entries.reduce((sum, entry) => sum + entry.documents.length, 0))
})
