import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/lesson': 'http://127.0.0.1:8000',
      '/audio': 'http://127.0.0.1:8000',
      '/diagram': 'http://127.0.0.1:8000',
    },
  },
})
