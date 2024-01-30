describe("Source dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit("/datasets/161d4b68-4b0d-4d96-80dc-d2f9867ff515");
    cy.injectAxe();
  });

  it("Check entire page for a11y issues", () => {
    cy.checkA11y();
  });
});
