import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
    outDir: "dist",
    rollupOptions: {
      input: {
        "index.tsx": resolve(__dirname, "src/index.tsx"),
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": { target: "http://127.0.0.1:6006", changeOrigin: true },
      "/graphql": { target: "http://127.0.0.1:6006", changeOrigin: true },
      "/healthz": { target: "http://127.0.0.1:6006", changeOrigin: true },
    },
  },
});
