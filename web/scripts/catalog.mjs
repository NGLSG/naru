import { readdir, readFile, stat } from 'node:fs/promises'
import { createReadStream } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const historicalRoot = fileURLToPath(new URL('../../historical/', import.meta.url))
const moduleId = 'virtual:archive-catalog'
const resolvedId = '\0' + moduleId

const archiveUrl = (id, name) => `/archive/${id.split('/').map(encodeURIComponent).join('/')}/${name.split('/').map(encodeURIComponent).join('/')}`

// Editorial captions are exhibit labels, not substitute historical sources.
// Dates refer to the selected exhibit/version; INDEX.md retains document dates.
const exhibits = {
  'fortran/ii-1958': ['FORTRAN', 'II · IBM 704', 1958, '把算式交给机器。', ['算式', '子程序', 'COMMON'], '#a77e45'],
  'algol/58': ['ALGOL', '58 / IAL', 1958, '寻找一种共同的语言。', ['算法', '初步报告'], '#77866c'],
  'algol/60': ['ALGOL', '60 · Revised Report', 1960, '思想开始拥有自己的结构。', ['块结构', '作用域', 'call-by-name'], '#77866c'],
  'cobol/60': ['COBOL', 'CODASYL · Original Report', 1960, '让数据接近人的叙述。', ['业务数据', 'PICTURE', 'PERFORM'], '#a87f62'],
  'lisp/1960-recursion': ['LISP', 'Recursive Functions', 1960, '表达式，也可以是数据。', ['S 表达式', 'quote', 'eval'], '#6b858c'],
  'lisp/1.5/1962': ['LISP', '1.5 · Programmer’s Manual', 1962, '在符号之间，生长出一个世界。', ['动态作用域', '符号表', '垃圾回收'], '#6b858c'],
  'basic/1964': ['BASIC', 'Dartmouth · First Manual', 1964, '从第一行，开始与机器对话。', ['交互环境', '行号', 'DTSS'], '#b36649'],
  'pli/1966': ['PL/I', 'IBM · Language Specifications', 1966, '把许多种可能，放进同一门语言。', ['属性', 'ON 条件', '存储类'], '#9a8a61'],
  'fortran/66': ['FORTRAN', '66 · ANSI X3.9', 1966, '把共同的约定写下来。', ['标准', '数值计算'], '#a77e45'],
  'bcpl': ['BCPL', 'Richards · Reference Manual', 1967, '从一个字，构造整个系统。', ['vector', 'OCODE', 'INTCODE'], '#9b785f'],
  'simula/67': ['SIMULA', '67 · Common Base', 1967, '为运行中的世界，赋予形状。', ['class', '引用', 'detach / resume'], '#737e99'],
  'basic/1968': ['BASIC', 'Dartmouth · Fourth Edition', 1968, '一段对话，容纳更多可能。', ['矩阵', '字符串', 'CHANGE'], '#b36649'],
  'apl/360': ['APL', '360 · Reference Manual', 1969, '让一组符号，说出整个数组。', ['数组', '归约', 'workspace'], '#848777'],
  'pascal/1970': ['Pascal', 'Wirth · Report Lineage', 1970, '把清晰，写进程序的结构。', ['类型', 'P-machine', 'Pascal-P'], '#868b64'],
  'b/1972': ['B', 'Bell Labs · Reference & Tutorial', 1972, '在简约之中，寻找系统的骨架。', ['字机器', '向量', '函数'], '#7b8180'],
  'c/kr/1978': ['C', 'Kernighan & Ritchie · First Edition', 1978, '一本书，一个仍在延伸的世界。', ['K&R', '旧式函数', 'PDP-11'], '#b45c3f'],
  'fortran/77': ['FORTRAN', '77 · ANSI X3.9–1978', 1978, '让旧的算式，走向新的机器。', ['标准', '数值计算'], '#a77e45'],
  'pascal/iso-1983': ['Pascal', 'ISO 7185 · Standard Pascal', 1983, '为一种清晰，建立共同的尺度。', ['ISO 7185', '一致性数组'], '#868b64'],
  'c/kr/1984': ['C', 'K&R · Vendor Dialects', 1984, '标准到来之前，有许多种 C。', ['厂商方言', '事实标准', 'Microsoft C'], '#b45c3f'],
  'c/89': ['C', 'ANSI C89 / ISO C90', 1989, '为共同使用，建立共同的边界。', ['标准草案', 'Rationale'], '#b45c3f'],
  'c/99': ['C', 'ISO C99 · Including TC3', 1999, '在熟悉的骨架上，继续生长。', ['N1256', '委员会草案'], '#b45c3f'],
  'c/11': ['C', 'ISO C11 · N1570', 2011, '时间继续，档案也继续。', ['N1570', '最终草案'], '#b45c3f'],
}

export function field(markdown, label) {
  const lines = markdown.replace(/\r\n?/g, '\n').split('\n')
  const start = lines.findIndex(line => line.startsWith(`- ${label}:`))
  if (start < 0) return ''
  const values = [lines[start].slice(label.length + 3).trim()]
  for (let i = start + 1; i < lines.length && /^\s+\S/.test(lines[i]) && !/^\s+-/.test(lines[i]); i++) values.push(lines[i].trim())
  return values.join(' ')
}

async function findIndexes(directory) {
  const items = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(items.filter(item => item.isDirectory()).map(item => findIndexes(path.join(directory, item.name))))
  return [...items.filter(item => item.isFile() && item.name === 'INDEX.md').map(item => path.join(directory, item.name)), ...nested.flat()]
}

async function findDocuments(directory, prefix = '') {
  const items = await readdir(directory, { withFileTypes: true })
  const files = items.filter(item => item.isFile() && /\.(pdf|txt|html?|htm)$/i.test(item.name)).map(item => ({ name: prefix + item.name }))
  for (const item of items.filter(item => item.isDirectory())) {
    const child = path.join(directory, item.name)
    // A nested entry owns its own documents; don't duplicate them in a parent.
    if ((await readdir(child)).includes('INDEX.md')) continue
    files.push(...await findDocuments(child, `${prefix}${item.name}/`))
  }
  return files.sort((a, b) => a.name.localeCompare(b.name))
}

export async function readCatalog(root = historicalRoot) {
  const indexes = await findIndexes(root)
  const entries = await Promise.all(indexes.map(async index => {
    const directory = path.dirname(index)
    const id = path.relative(root, directory).split(path.sep).join('/')
    const markdown = await readFile(index, 'utf8')
    const title = markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? id
    const yearLabel = field(markdown, '年份')
    const editorial = exhibits[id] ?? [id.split('/')[0].toUpperCase(), title, Number(yearLabel.match(/\b(19|20)\d{2}\b/)?.[0]) || 0, '一份等待重新阅读的语言档案。', [], '#7b8180']
    const [label, variant, year, caption, keywords, color] = editorial
    const files = await findDocuments(directory)
    // Expose historical HTML as plain text in static builds as well as development.
    // Its bytes and download filename remain the original; it is not executable site code.
    const documents = await Promise.all(files.map(async file => ({ name: file.name, url: archiveUrl(id, /\.html?$/i.test(file.name) ? `${file.name}.txt` : file.name),
      bytes: (await stat(path.join(directory, file.name))).size, format: path.extname(file.name).slice(1).toUpperCase() })))
    let notesMarkdown = ''
    try { notesMarkdown = await readFile(path.join(directory, 'notes.md'), 'utf8') } catch (error) { if (error.code !== 'ENOENT') throw error }
    return { id, family: id.split('/')[0], label, variant, year, yearLabel, title, caption, keywords, color,
      author: field(markdown, '主体/作者'), kind: field(markdown, '类型'), subject: field(markdown, '考据对象'),
      license: field(markdown, '许可'), relationship: field(markdown, '与 Naru 方言的关系'), remarks: field(markdown, '备注'),
      sources: [...new Set((field(markdown, '来源').match(/https?:\/\/[^\s<>，；;、)）]+/g) ?? []).map(url => url.replace(/[.,]$/, '')))],
      documents, indexUrl: archiveUrl(id, 'INDEX.md'), indexMarkdown: markdown, notesMarkdown }
  }))
  entries.sort((a, b) => a.year - b.year || a.id.localeCompare(b.id))
  return { entries, families: [...new Set(entries.map(entry => entry.family))], documentCount: entries.reduce((sum, entry) => sum + entry.documents.length, 0) }
}

export function archivePlugin() {
  let catalog
  let available = new Map()
  async function refresh() {
    catalog = await readCatalog()
    available = new Map(catalog.entries.flatMap(entry => [
      [entry.indexUrl, path.join(historicalRoot, entry.id, 'INDEX.md')],
      ...(entry.notesMarkdown ? [[archiveUrl(entry.id, 'notes.md'), path.join(historicalRoot, entry.id, 'notes.md')]] : []),
      ...entry.documents.map(document => [document.url, path.join(historicalRoot, entry.id, document.name)]),
    ]))
  }
  return {
    name: 'naru-historical-catalog',
    async buildStart() { await refresh() },
    resolveId(id) { if (id === moduleId) return resolvedId },
    async load(id) { if (id === resolvedId) { if (!catalog) await refresh(); return `export default ${JSON.stringify(catalog)}` } },
    configureServer(server) {
      server.watcher.add(historicalRoot)
      let timer
      const update = file => {
        if (!file.startsWith(historicalRoot)) return
        clearTimeout(timer)
        timer = setTimeout(async () => {
          try {
            await refresh()
            const module = server.moduleGraph.getModuleById(resolvedId)
            if (module) server.moduleGraph.invalidateModule(module)
            server.ws.send({ type: 'full-reload' })
          } catch (error) { server.config.logger.error(`Archive reload failed: ${error.message}`) }
        }, 80)
      }
      for (const event of ['add', 'change', 'unlink']) server.watcher.on(event, update)
      server.httpServer?.once('close', () => clearTimeout(timer))
      server.middlewares.use(async (request, response, next) => {
        const url = request.url?.split('?')[0]
        const file = available.get(url)
        if (!file) {
          if (!url?.startsWith('/archive/')) return next()
          response.statusCode = 404
          return response.end('Archive document not found')
        }
        if (!['GET', 'HEAD'].includes(request.method)) {
          response.statusCode = 405
          response.setHeader('Allow', 'GET, HEAD')
          return response.end()
        }
        try {
          const ext = path.extname(file).toLowerCase()
          response.setHeader('Content-Type', ext === '.pdf' ? 'application/pdf' : 'text/plain; charset=utf-8')
          response.setHeader('X-Content-Type-Options', 'nosniff')
          response.setHeader('Content-Length', (await stat(file)).size)
          if (request.method === 'HEAD') return response.end()
          const stream = createReadStream(file)
          response.once('close', () => stream.destroy())
          stream.on('error', next)
          stream.pipe(response)
        } catch (error) { next(error) }
      })
    },
    async generateBundle() {
      for (const [url, file] of available) {
        this.emitFile({ type: 'asset', fileName: decodeURIComponent(url.slice(1)), source: await readFile(file) })
      }
    },
  }
}
