import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@weather/protocol": path.resolve(__dirname, "../protocol/src/index.ts"),
    },
  },
  server: {
    proxy: {
      "/forecast": "http://localhost:8080",
    },
  },
});
