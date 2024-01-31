import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    specPattern: "cypress/a11y/**/*.cy.{js,jsx,ts,tsx}",
    supportFile: "cypress/support/a11y.ts",
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
