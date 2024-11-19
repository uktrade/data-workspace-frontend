import "@testing-library/cypress/add-commands";
import "./setup-cypress-testing-library";
/// <reference types="cypress" />

Cypress.Commands.add("setUsersEditorAccess", (dataSetId, hasEditorAccess) => {
  // First go to home page to pick up CSRF cookie
  cy.visit("/");
  cy.getCookie("data_workspace_csrf").then((c) =>
    cy.request({
      url: `/test/dataset/${dataSetId}`,
      method: "PATCH",
      headers: {
        "X-CSRFToken": c.value,
      },
      body: {
        data_catalogue_editors: [hasEditorAccess ? 2 : 1],
      },
    })
  );
});
