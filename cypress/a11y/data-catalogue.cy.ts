describe("Data catalogue page", () => {
  beforeEach(() => {
    cy.visit(`/datasets`);
    cy.injectAxe();
  });

  it("Check entire page for a11y issues", () => {
    cy.checkA11y();
  });
});
