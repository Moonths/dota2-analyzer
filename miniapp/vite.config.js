import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    proxy: {
      '/dota-api': {
        target: 'https://maojike.me',
        changeOrigin: true,
      },
    },
  },
})
