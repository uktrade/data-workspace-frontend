describe("Source dataset catalogue page", () => {
  beforeEach(() => {
    cy.visit("/datasets/161d4b68-4b0d-4d96-80dc-d2f9867ff515");
  });

  it("should have a title", () => {
    cy.contains("h1", "Data cut - links");
  });
});
