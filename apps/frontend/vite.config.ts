import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In Docker, use the service name; locally, use localhost
const isDocker = process.env.DOCKER === 'true'
const apiTarget = isDocker ? 'http://copilot-backend:8002' : 'http://localhost:8002'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true, // Allow external connections in Docker
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
