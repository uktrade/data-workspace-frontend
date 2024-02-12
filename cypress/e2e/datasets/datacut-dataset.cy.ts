import { datacutWithLinks } from "../../fixtures/datasets";

describe("Datacut dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit(`/datasets/${datacutWithLinks}`);
  });

  it("should have a title", () => {
    cy.contains("h1", "Data cut - links");
  });
});
