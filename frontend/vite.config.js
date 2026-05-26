import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";

export default defineConfig({
  plugins: [vue(), process.env.NODE_ENV === "development" ? vueDevTools() : null].filter(Boolean),
  optimizeDeps: {
    include: ["vue", "vue-router"],
  },
  esbuild: {
    target: "es2020",
  },
  build: {
    target: "es2020",
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    warmup: {
      clientFiles: ["./src/main.js", "./src/App.vue", "./src/pages/DigitalHumanVideo.vue"],
    },
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
