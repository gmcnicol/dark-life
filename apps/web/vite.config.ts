import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
// @ts-expect-error Vite executes this runtime-only server helper directly from ESM.
import { handleAdminProxy, isAdminProxyRequest } from "./server/admin-proxy.mjs";

export default defineConfig({
  envDir: "../..",
  plugins: [
    react(),
    {
      name: "dark-life-admin-proxy",
      configureServer(server) {
        const apiBase = process.env.API_PROXY_TARGET || "http://localhost:8000";
        server.middlewares.use(async (req, res, next) => {
          if (!isAdminProxyRequest(req.url || "")) {
            next();
            return;
          }
          await handleAdminProxy(req, res, { apiBase });
        });
      },
    },
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 3000,
  },
});
