import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `--mode sample` runs on the sample account (see src/sample/sampleAccount.ts),
// on its own port so its remembered Game Filters stay apart from the real app's
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    port: mode === "sample" ? 5174 : 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
}));
