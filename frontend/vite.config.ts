import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Build to frontend/dist (gitignored); the packaging build hook copies it into
// src/argus/dashboard/static for the wheel. Relative base so the bundle works
// regardless of the mount path. The dev server proxies API calls to the bot.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": "http://localhost:9191",
      "/metrics": "http://localhost:9191",
    },
  },
  test: {
    setupFiles: ["./src/test-setup.ts"],
  },
});
