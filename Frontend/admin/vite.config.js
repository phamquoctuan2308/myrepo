import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

function requireBuildUrl(env, name) {
  const value = env[name]?.trim()
  if (!value) throw new Error(`${name} must be set for a production build`)
  const url = new URL(value)
  const isLocal = ['localhost', '127.0.0.1'].includes(url.hostname)
  if (url.protocol !== 'https:' && !isLocal) {
    throw new Error(`${name} must use https outside localhost`)
  }
}

export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    const env = loadEnv(mode, projectRoot, '')
    requireBuildUrl(env, 'VITE_API_BASE_URL')
    requireBuildUrl(env, 'VITE_USER_APP_URL')
  }
  return { plugins: [react()], server: { port: 5174 } }
})
