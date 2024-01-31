import { datacutWithLinks } from "../../fixtures/datasets";

describe("Source dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit(`/datasets/${datacutWithLinks}`);
  });

  it("should have a title", () => {
    cy.contains("h1", "Data cut - links - FORCE FAIL");
  });
});
