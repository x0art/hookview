import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// The bundle is served by FastAPI from static/app, so asset URLs are relative
// to /app/. `base` must match the mount point or the hashed asset paths 404.
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: resolve(__dirname, "../static/app"),
    emptyOutDir: true,
    // A single predictable entry file keeps the index.html script tag stable
    // across rebuilds, so committing build output never churns the tag.
    rollupOptions: {
      output: {
        entryFileNames: "island.js",
        chunkFileNames: "chunk-[hash].js",
        assetFileNames: "island[extname]",
      },
    },
    target: "es2020",
  },
});
