import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

const DEV_API = 'http://localhost:8000'
const PROD_HOST = 'https://maojike.me'

export default defineConfig(({ mode }) => {
  const isDev = mode === 'development'
  return {
    plugins: [uni()],
    define: {
      __API_BASE__: JSON.stringify(isDev ? DEV_API + '/api' : PROD_HOST + '/dota-api'),
      __IMG_HOST__: JSON.stringify(isDev ? DEV_API : PROD_HOST),
    },
    server: {
      proxy: {
        '/dota-api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/dota-api/, '/api'),
        },
      },
    },
  }
})
