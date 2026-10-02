import {defineConfig} from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser", workers: 1, timeout: 60000,
  use: {baseURL: "http://127.0.0.1:3001", browserName: "chromium", channel: "msedge", headless: true, screenshot: "only-on-failure", trace: "retain-on-failure"},
  webServer: [
    {command: `${process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python"} scripts/e2e_server.py`, url: "http://127.0.0.1:8011/health", reuseExistingServer: false, timeout: 60000},
    {command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3001", url: "http://127.0.0.1:3001", env: {BACKEND_URL: "http://127.0.0.1:8011", NEXT_TELEMETRY_DISABLED: "1", NEXT_DIST_DIR: ".next-e2e"}, reuseExistingServer: false, timeout: 60000},
  ],
});
