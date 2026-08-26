import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Tailwind is scoped to this app only (Frontend/admin has its own separate vite.config.js and
// does not get this plugin) - see Frontend/user/src/orbit-tailwind.css for why preflight is
// skipped (Bootstrap 5 is still the base design system; Tailwind only adds utility classes for
// the new sci-fi surfaces).
export default defineConfig({ plugins: [react(), tailwindcss()], server: { port: 5173 } })
