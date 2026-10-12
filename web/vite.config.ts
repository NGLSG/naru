import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { archivePlugin } from './scripts/catalog.mjs'
import { wikiPlugin } from './scripts/wiki.mjs'

export default defineConfig({
  plugins: [vue(), archivePlugin(), wikiPlugin()],
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
})
