/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    env: { VITE_USE_MOCKS: "true" },
    // jsdom suites run in parallel; the 5 s default times out in resource-limited
    // containers (docker compose run frontend-tests) although every test passes locally.
    testTimeout: 20_000,
    // Node --test scripts under scripts/ (e.g. openapi-equal) are not Vitest suites.
    exclude: ["**/node_modules/**", "**/dist/**", "scripts/**"],
  },
});
