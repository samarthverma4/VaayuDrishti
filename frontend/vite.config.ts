import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5180,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  // MapLibre v6 loads its worker relative to its own module URL; pre-bundling breaks that path.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  build: { chunkSizeWarningLimit: 1500 },
})
