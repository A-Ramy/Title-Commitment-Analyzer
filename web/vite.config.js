import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  build: {
    target: 'es2020', sourcemap: false, chunkSizeWarningLimit: 700,
    rollupOptions: { output: { manualChunks: id => (/node_modules\/@?firebase/.test(id) ? 'firebase' : undefined) } },
  },
  server: { port: 5173, host: '127.0.0.1' },
  preview: { port: 5173, host: '127.0.0.1' },
});
