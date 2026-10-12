/// <reference types="vite/client" />

declare module 'virtual:archive-catalog' {
  const catalog: import('./types').ArchiveCatalog
  export default catalog
}
declare module 'virtual:archive-wiki' {
  const wiki: import('./types').WikiCatalog
  export default wiki
}
