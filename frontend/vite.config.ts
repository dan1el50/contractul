import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
// defineConfig comes from vitest/config, not vite — it is the same function
// widened to accept the `test` block below. Importing it from 'vite' typechecks
// everything else fine and then rejects `test` as an unknown property.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
  plugins: [react()],
  resolve: {
    // Mirrors the `paths` mapping in tsconfig.json. Both are needed: tsconfig
    // teaches the type checker, this teaches the bundler.
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true, // bind 0.0.0.0 — without this the dev server is unreachable from outside the container
    port: 5173,
    watch: {
      // Filesystem events do not cross the container boundary reliably on
      // Windows or macOS bind mounts, so the watcher never fires and edits
      // appear to do nothing. Polling is slower but actually works.
      usePolling: true,
      interval: 300,
    },
  },
})
