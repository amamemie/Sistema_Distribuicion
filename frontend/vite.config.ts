/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// `--mode demo`: versión de demostración para GitHub Pages (sin servidor, datos de ejemplo).
export default defineConfig(({ mode }) => ({
  base: mode === 'demo' ? '/Sistema_Distribuicion/' : '/',
  build: mode === 'demo' ? { outDir: 'dist-demo' } : undefined,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      disable: mode === 'demo',
      registerType: 'autoUpdate',
      includeAssets: ['icono.svg'],
      manifest: {
        name: 'Sistema de Inventario',
        short_name: 'Inventario',
        description: 'Inventario, pedidos y rentabilidad',
        lang: 'es',
        theme_color: '#0f766e',
        background_color: '#f6f7f9',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: '/icono.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: {
        // La API nunca se sirve desde caché: los datos de inventario deben ser actuales.
        navigateFallbackDenylist: [/^\/api\//],
      },
    }),
  ],
  server: {
    // API_PROXY permite apuntar a otra instancia (p. ej. una copia de prueba en :8091).
    proxy: { '/api': process.env.API_PROXY ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'node',
  },
}))
