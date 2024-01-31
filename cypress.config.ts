import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: "http://dataworkspace.test:8000",
    screenshotsFolder: "test-results/screenshots",
    video:true,
    videosFolder: "test-results/videos",
    viewportWidth: 1200,
    viewportHeight: 900,
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});
