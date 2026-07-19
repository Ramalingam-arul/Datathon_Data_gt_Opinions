import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',          // relative asset paths — required for Catalyst web hosting
  build: { outDir: 'dist' }
})
