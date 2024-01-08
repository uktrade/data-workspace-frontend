import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: Cypress.env('baseUrl'),
    viewportWidth: 1200,
    viewportHeight: 900,
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    video: true,
  },
});
