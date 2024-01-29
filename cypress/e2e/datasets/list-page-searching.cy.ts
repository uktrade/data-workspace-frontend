describe("Dataset list page searching", () => {
  beforeEach(() => {
    cy.intercept("GET", "datasets/?q=*").as("api_search");
    cy.visit("/datasets/");
  });

  context("When searching for datasets by name with a match", () => {
    it("should only show datasets matching the searched name", () => {
      cy.findByPlaceholderText("Search by dataset name or description").type(
        "source"
      );
      cy.findByRole("button", { name: "Search" }).click();
      cy.wait("@api_search");

      cy.findAllByTestId("search-result")
        .should("have.length", 3)
        .each(($el) => {
          cy.wrap($el).should("have.attr", "href").should("contain", "source");
        });
    });
  });

  context("When searching for datasets by name without a match", () => {
    it("should not show any results", () => {
      cy.findByPlaceholderText("Search by dataset name or description").type(
        "ABCDEF"
      );
      cy.findByRole("button", { name: "Search" }).click();
      cy.wait("@api_search");

      cy.findAllByTestId("search-result").should("have.length", 0);
    });
  });
});
