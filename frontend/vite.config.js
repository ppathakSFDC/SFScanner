import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8080',
      '/scan': 'http://localhost:8080',
      '/setup': 'http://localhost:8080',
      '/agents': 'http://localhost:8080',
      '/chat': 'http://localhost:8080',
      '/migrate': 'http://localhost:8080',
      '/health': 'http://localhost:8080',
    },
  },
})
