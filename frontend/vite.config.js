import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ command }) => {
  const backendTarget = (process.env.VITE_BACKEND_TARGET || "http://127.0.0.1:8001").replace(/\/$/, "");
  const bindHost = process.env.FRONTEND_BIND_HOST || "127.0.0.1";

  return {
    base: command === "build" ? "/app/" : "/",
    plugins: [vue()],
    server: {
      host: bindHost,
      port: 5173,
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
        "/ws": {
          target: backendTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    preview: {
      host: bindHost,
      port: 4173,
    },
    build: {
      manifest: true,
    },
  };
});
