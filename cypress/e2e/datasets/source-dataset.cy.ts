import { sourceWithTable } from "../../fixtures/datasets";

describe("Source dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit(`/datasets/${sourceWithTable}`);
  });

  it("should have a title", () => {
    cy.contains("h1", "Source dataset a");
  });
});
