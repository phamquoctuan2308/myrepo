import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

function requireBuildUrl(env, name, protocols) {
  const value = env[name]?.trim()
  if (!value) throw new Error(`${name} must be set for a production build`)
  const url = new URL(value)
  const isLocal = ['localhost', '127.0.0.1'].includes(url.hostname)
  if (!protocols.includes(url.protocol) && !isLocal) {
    throw new Error(`${name} must use ${protocols.join(' or ')} outside localhost`)
  }
}

export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    const env = loadEnv(mode, projectRoot, '')
    requireBuildUrl(env, 'VITE_API_BASE_URL', ['https:'])
    requireBuildUrl(env, 'VITE_WS_BASE_URL', ['wss:'])
    requireBuildUrl(env, 'VITE_ADMIN_APP_URL', ['https:'])
  }
  return {
    plugins: [react()],
    devtools: false,
    server: { port: 5173 },
  }
})
