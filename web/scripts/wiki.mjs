import { readFile, readdir, stat } from 'node:fs/promises'
import { createReadStream } from 'node:fs'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const projectRoot = fileURLToPath(new URL('../../', import.meta.url))
const moduleId = 'virtual:archive-wiki'
const resolvedId = '\0' + moduleId
// Plain-text suffix makes rule/example reading portable to static hosts too.
const urlFor = file => '/implementation/' + file.split('/').map(encodeURIComponent).join('/') + (/\.(json|txt)$/.test(file) ? '' : '.txt')
const descriptions = {
  base: ['语言基础', '函数、表达式与整程序基础规则'], types: ['语言基础', '类型描述与类型关系'], numbers: ['语言基础', '数值系统与运算选择'],
  pipeline: ['编译设施', '可组合编译管线'], tree: ['编译设施', '树遍历与改写'], parse: ['编译设施', '解析选择与消歧工具'], headers: ['编译设施', '系统头文件发现'], layout: ['编译设施', '数据布局工具'],
  ownership: ['资源与行为', '所有权与资源状态'], resources: ['资源与行为', '资源效果规则'], loops: ['资源与行为', '循环与所有权组合'], unless: ['资源与行为', 'unless 表面语法'],
  control: ['控制与调用', '结构化控制流'], control_flow: ['控制与调用', '控制流示例方言'], cfg: ['控制与调用', '标签与基本块控制流'], functions: ['控制与调用', '函数设施'], closures: ['控制与调用', '闭包与捕获'], defer: ['资源与行为', '延迟清理'], externc: ['控制与调用', 'C ABI 外部调用'],
  arrays: ['数据与抽象', '数组组合规则'], affine: ['数据与抽象', 'Affine 运算与循环'], records: ['数据与抽象', '记录与字段'], shapes: ['数据与抽象', '形状描述'], variants: ['数据与抽象', '变体类型'], patterns: ['数据与抽象', '模式匹配'], generics: ['数据与抽象', '泛型规则'], constraints: ['数据与抽象', '约束关系'], traits: ['数据与抽象', '特征关系'], operators: ['数据与抽象', '运算符语义分派'],
  b: ['历史语言', 'MH-TSS B · 1972 语义目标'], pascal: ['历史语言', 'ISO 7185 Pascal 目标子集'], c11: ['历史语言', 'C11 原始文件与整程序入口'], composed: ['组合入口', 'C11 与初始化模块的组合入口'], standard: ['组合入口', '标准规则组组合入口'],
  custom_device: ['后端与示例', '自定义设备方言示例'], native_device: ['后端与示例', '设备后端示例'], alternate: ['后端与示例', '替代表面语法'], money: ['后端与示例', '金额运算规则'],
}
const implementations = {
  b: { name: 'B · 1972 目标', module: 'b', frontend: 'b.frontend', status: '规则存在 · 忠实度待补齐',
    summary: '独立 B 词法和字模型，组合 base、types、numbers、pipeline、tree、cfg。',
    features: ['无类型 i64 字表达式', '17 种历史赋值形式', 'auto / extrn 与向量', 'if / while、函数与递归', 'goto / 标签、字符与字符串设施'],
    limits: ['并非原 Honeywell 位宽与完整运行库。', '外部向量名重绑定和取地址尚无地址槽，现明确拒绝；元素读写已有回归。', '方言调试回归不等于完整历史一致性，详见调试记录。'],
    files: ['dialects/b.stx', 'docs/b.md', 'docs/dialect-debug.md', 'examples/b/Naru.toml'], examples: ['examples/b/vector.b', 'examples/b/recursion.b', 'examples/b/string.b'],
    command: '.\\target\\naru.exe build --project examples\\b --target exe -o target\\b-example.exe' },
  pascal: { name: 'Pascal · ISO 7185 目标子集', module: 'pascal', frontend: 'pascal.frontend', status: '规则存在 · 标准子集',
    summary: '独立 Pascal 扫描、program 展开和函数结果规则；复用基础类型、数值与管线。',
    features: ['program、var、const', '值参数函数与过程', 'integer / boolean / real', 'if、while、for、case', 'write / writeln 与字符串输出'],
    limits: ['集合、记录、嵌套作用域与完整文件语义未补齐。', '实除、大小写、全局变量和编译期只读常量已有回归；完整声明顺序与参数规则仍有缺口。', 'halt 属扩展，不作 ISO 行为保证；早期 Wirth 模式未独立实现。'],
    files: ['dialects/pascal.stx', 'docs/pascal.md', 'docs/dialect-debug.md'], examples: ['examples/pascal/showcase.pas', 'examples/pascal/dangling_else.pas'],
    command: '.\\target\\naru.exe build examples\\pascal\\showcase.pas --rules dialects\\pascal.stx --frontend pascal.frontend --runtime crt-static --target exe -o target\\pascal-showcase.exe' },
  c11: { name: 'C11 · Windows x64', module: 'c11', frontend: 'c11.frontend', status: '规则存在 · 有压力测试记录',
    summary: '原始 .c 文件入口，预处理、声明器、类型、对象、布局与初始化模块组合；使用系统头文件和 CRT。',
    features: ['#include 与宏预处理', '复杂声明器与函数指针', '结构 / 联合与布局', '初始化与枚举、控制流', '系统头文件、系统 CRT 与真实项目测试'],
    limits: ['保存的压力测试不等于完整 C11 标准一致性。', '测试宿主为 Windows x64 / LLP64。', 'K&R、C89 与 C99 尚无独立的历史规则入口与验收。'],
    files: ['dialects/c11.stx', 'dialects/c11-composed.stx', 'docs/dialect-debug.md', 'tests/c11_stress.py'], examples: ['tests/c11/cases/system_io.c', 'tests/c11/cases/declarators.c'],
    command: '.\\target\\naru.exe build tests\\c11\\cases\\system_io.c --rules dialects\\c11.stx --frontend c11.frontend --unit program --relation c11.emit_program --runtime crt-static --target exe -o target\\c11-system-io.exe' },
}

async function ruleFiles(dir) {
  const items = await readdir(dir, { withFileTypes: true })
  const nested = await Promise.all(items.filter(item => item.isDirectory()).map(item => ruleFiles(path.join(dir, item.name))))
  return [...items.filter(item => item.isFile() && item.name.endsWith('.stx')).map(item => path.join(dir, item.name)), ...nested.flat()].sort()
}
export async function readWiki() {
  const editorial = new URL('../content/encyclopedia.mjs', import.meta.url)
  const editedAt = (await stat(fileURLToPath(editorial))).mtime.toISOString()
  const { families, versions } = await import(`${editorial.href}?mtime=${encodeURIComponent(editedAt)}`)
  const available = new Map()
  function expose(file) { const url = urlFor(file); available.set(url, path.join(projectRoot, file)); return { path: file, url } }
  const modules = await Promise.all((await ruleFiles(path.join(projectRoot, 'dialects'))).map(async file => {
    const text = await readFile(file, 'utf8')
    const name = text.match(/^mod\s+([\w.]+)\s*;/m)?.[1] ?? path.basename(file, '.stx')
    const relative = path.relative(projectRoot, file).split(path.sep).join('/')
    const imports = [...text.matchAll(/^use\s+([\w.]+)\s*;/gm)].map(match => match[1])
    const [category, description] = descriptions[name] ?? (name.startsWith('c11.') ? ['C11 组成模块', `C11 · ${name.slice(4)} 规则`] : ['其他规则', '工作区中的规则模块'])
    return { name, ...expose(relative), imports, category, description,
      syntaxCount: [...text.matchAll(/^syntax\s/gm)].length, effectCount: [...text.matchAll(/^effect(?:\s|\[)/gm)].length,
      frontends: [...text.matchAll(/^effect\s+([\w.]+\.frontend)\s*\(/gm)].map(match => match[1]),
      sha256: createHash('sha256').update(text).digest('hex') }
  }))
  const byName = new Map(modules.filter(item => !item.path.endsWith('-nobranch.stx')).map(item => [item.name, item]))
  function closure(name, seen = new Set()) {
    if (seen.has(name) || !byName.has(name)) return seen
    seen.add(name)
    for (const imported of byName.get(name).imports) closure(imported, seen)
    return seen
  }
  const resolved = {}
  for (const [key, value] of Object.entries(implementations)) {
    const files = value.files.map(expose)
    for (const file of files) await stat(path.join(projectRoot, file.path))
    const examples = await Promise.all(value.examples.map(async file => ({ ...expose(file), code: await readFile(path.join(projectRoot, file), 'utf8') })))
    resolved[key] = { ...value, files, examples, modules: [...closure(value.module)] }
  }
  let report
  const reportPath = 'target/c11-stress-current.json'
  try {
    const raw = JSON.parse(await readFile(path.join(projectRoot, reportPath), 'utf8'))
    report = { url: expose(reportPath).url, recordedAt: (await stat(path.join(projectRoot, reportPath))).mtime.toISOString(),
      passed: raw.passed, total: raw.total, cases: raw.results.map(item => ({ name: item.name, passed: item.passed })) }
  } catch (error) { if (error.code !== 'ENOENT') throw error }
  return { catalog: { families, versions, modules, implementations: resolved, report, editedAt }, available }
}

export function wikiPlugin() {
  let catalog, available = new Map()
  async function refresh() { ({ catalog, available } = await readWiki()) }
  return {
    name: 'naru-encyclopedia', async buildStart() { await refresh() },
    resolveId(id) { if (id === moduleId) return resolvedId },
    async load(id) { if (id === resolvedId) { if (!catalog) await refresh(); return `export default ${JSON.stringify(catalog)}` } },
    configureServer(server) {
      const watched = [path.join(projectRoot, 'dialects'), path.join(projectRoot, 'docs'), path.join(projectRoot, 'examples'), path.join(projectRoot, 'web/content'), path.join(projectRoot, 'target/c11-stress-current.json')]
      server.watcher.add(watched)
      let timer
      const update = file => {
        if (!watched.some(root => file.startsWith(root))) return
        clearTimeout(timer)
        timer = setTimeout(async () => {
          try { await refresh(); const mod = server.moduleGraph.getModuleById(resolvedId); if (mod) server.moduleGraph.invalidateModule(mod); server.ws.send({ type: 'full-reload' }) }
          catch (error) { server.config.logger.error(`Wiki reload failed: ${error.message}`) }
        }, 120)
      }
      for (const event of ['add', 'change', 'unlink']) server.watcher.on(event, update)
      server.httpServer?.once('close', () => clearTimeout(timer))
      server.middlewares.use(async (request, response, next) => {
        const url = request.url?.split('?')[0]
        if (!url?.startsWith('/implementation/')) return next()
        const file = available.get(url)
        if (!file) { response.statusCode = 404; return response.end('Evidence not found') }
        if (!['GET', 'HEAD'].includes(request.method)) { response.statusCode = 405; response.setHeader('Allow', 'GET, HEAD'); return response.end() }
        response.setHeader('Content-Type', 'text/plain; charset=utf-8')
        response.setHeader('X-Content-Type-Options', 'nosniff')
        response.setHeader('Content-Length', (await stat(file)).size)
        if (request.method === 'HEAD') return response.end()
        const stream = createReadStream(file); response.once('close', () => stream.destroy()); stream.on('error', next); stream.pipe(response)
      })
    },
    async generateBundle() { for (const [url, file] of available) this.emitFile({ type: 'asset', fileName: decodeURIComponent(url.slice(1)), source: await readFile(file) }) },
  }
}
