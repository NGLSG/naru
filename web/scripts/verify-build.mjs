import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { readCatalog, historicalRoot } from './catalog.mjs'
import { readWiki } from './wiki.mjs'

const outputRoot = fileURLToPath(new URL('../dist/', import.meta.url))
const catalog = await readCatalog()
const digest = bytes => createHash('sha256').update(bytes).digest('hex')
let verified = 0
for (const entry of catalog.entries) {
  const assets = [{ name: 'INDEX.md', url: entry.indexUrl }, ...entry.documents]
  if (entry.notesMarkdown) assets.push({ name: 'notes.md', url: entry.indexUrl.replace('INDEX.md', 'notes.md') })
  for (const asset of assets) {
    const original = await readFile(path.join(historicalRoot, entry.id, asset.name))
    const built = await readFile(path.join(outputRoot, decodeURIComponent(asset.url.slice(1))))
    assert.equal(digest(built), digest(original), `Original archive bytes changed: ${asset.url}`)
    if (/\.html?$/i.test(asset.name)) assert.ok(asset.url.endsWith('.txt'), asset.url)
    verified++
  }
}
console.log(`${verified} archive assets verified against their originals (SHA-256).`)
const { available } = await readWiki()
for (const [url, file] of available) {
  const original = await readFile(file)
  const built = await readFile(path.join(outputRoot, decodeURIComponent(url.slice(1))))
  assert.equal(digest(built), digest(original), `Implementation snapshot differs: ${url}`)
}
console.log(`${available.size} implementation sources and saved reports verified (SHA-256).`)
