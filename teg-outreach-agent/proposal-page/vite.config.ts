/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  base: "/static/proposal/",
  plugins: [react()],
  build: { outDir: "../app/static/proposal", emptyOutDir: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
