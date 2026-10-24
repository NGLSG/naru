# 语言数字档案馆

Vue 3 + TypeScript + Vite。首页以横向时间线呈现语言和版本，文章按语言谱系组织。字体和语言标志本地加载。

## 开发与构建

需要 Node.js 22.12+ 或 24+。

```powershell
cd web
npm ci
npm run dev
```

开发地址为 http://127.0.0.1:5173/ 。

```powershell
npm run check:archive
npm run check:wiki
npm run build
npm run check:build
npm run preview
```

构建产物位于 `web/dist/`，预览地址为 http://127.0.0.1:4173/ 。页面使用 hash 路由，静态部署时保留 `assets/`、`archive/` 和 `implementation/`。

## 内容与来源

| 文件 | 职责 |
| --- | --- |
| `content/encyclopedia.mjs` | 语言正文、版本导读、专节与引文 |
| `scripts/catalog.mjs` | 从 `historical/**/INDEX.md`、注记和原件生成馆藏目录 |
| `scripts/wiki.mjs` | 收集方言模块、导入关系、源码快照和示例 |
| `src/components/LanguageMark.vue` | 语言标志 |
| `src/components/LanguageTrace.vue` | 背景示例语法与年代水印 |
| `src/style.css` | 排版、颜色与布局 |

新增档案时补充对应的百科正文和版本记录。时间线使用语言或版本年代，资料框保留文献本身的年代。测试报告按生成日期展示，网站构建不运行编译器测试。

源码预览包不附史料原件，`historical/source-preview.json` 记录省略的文件。此时文章保留正文和条目卡，引文链接至来源卡；完整资料工作区则提供本地原件下载。

构建按原始字节复制资料。HTML 原件的公开路径追加 `.txt`，下载保留原文件名，避免作为网页脚本执行。

语言标志来源及版本见 `public/language-marks/SOURCES.md`，许可证随构建保留。现代社区标志用于识别语言。背景代码是装饰示例，对辅助技术隐藏。

## 路由与检查

- `#/language/basic`：语言总览。
- `#/archive/basic%2F1964`：版本文章。
- `#/index`：正文搜索与版本目录。
- `#/dialects`：规则库、导入关系及源码。

`check:archive` 检查目录与文件关联，`check:wiki` 检查文章、引文、版本和服务端渲染，`check:build` 核对资料及源码快照的 SHA-256。

共建表单下载本地 Markdown 草稿。社区提交、账户、审核和在线编译服务尚未接入。
