import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 1100 },
  },
  webServer: [
    {
      command:
        process.platform === "win32"
          ? ".venv\\Scripts\\python.exe scripts/e2e_backend.py"
          : ".venv/bin/python scripts/e2e_backend.py",
      url: "http://127.0.0.1:8010/api/health",
      env: {
        DATABASE_URL: "sqlite:///./data/e2e.db",
        MEDIA_DIR: "./data/e2e-media",
        DEMO_MODE: "true",
        OPERATOR_TOKEN: "",
        REDIS_URL: "",
        S3_ENDPOINT: "",
      },
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174",
      env: { API_URL: "http://127.0.0.1:8010" },
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
});
