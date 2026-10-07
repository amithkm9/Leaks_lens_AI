import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testDir: "./screenshots",
  outputDir: "./test-results/readme",
  timeout: 90000,
  use: {
    ...base.use,
    viewport: { width: 1440, height: 1050 },
    locale: "en-GB",
    timezoneId: "UTC",
  },
  projects: [
    {
      name: "readme",
      use: {
        browserName: "chromium",
        channel: process.env.CI ? undefined : "chrome",
        deviceScaleFactor: 1,
      },
    },
  ],
});
