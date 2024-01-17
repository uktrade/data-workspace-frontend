describe("Source dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit("/datasets/7519f281-ed5f-4c9d-b113-c1d4a60c0d1e");
    cy.injectAxe();
  });

  it("Check entire page for a11y issues", () => {
    cy.checkA11y();
  });

  it("should have a title", () => {
    cy.contains("h1", "Test data cut dataset");
  });
});
