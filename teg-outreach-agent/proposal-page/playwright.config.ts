import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:4178" },
  webServer: {
    command: "node e2e/server.mjs",
    url: "http://127.0.0.1:4178/health",
    reuseExistingServer: false,
    timeout: 10000,
  },
});
