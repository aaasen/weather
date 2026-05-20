import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/forecast": "http://localhost:8080",
    },
  },
});
