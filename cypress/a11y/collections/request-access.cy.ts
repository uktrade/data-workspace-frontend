import { personalCollection } from "../../fixtures/collections";

describe("Request access to collections page", () => {
  beforeEach(() => {
    cy.visit(`/collections/${personalCollection}/request_collection_access`);
    cy.injectAxe();
  });

  it("Check entire page for a11y issues", () => {
    cy.checkA11y();
  });
});
