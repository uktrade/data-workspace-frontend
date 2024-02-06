import { datacutWithLinks } from "../../fixtures/datasets";

describe("Dialog notification", () => {
  context("When a user downloads data", () => {

    it("should show a banner notification", () => {
      cy.intercept("GET", "**/download.csv", {
        statusCode: 200,
        body: '',
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename=source_link1.csv'
        }
      }).as("getDownload");
      
      cy.visit(`/datasets/${datacutWithLinks}`);
      cy.findByRole("link", { name: "source_link1" }).click();
      cy.findByRole("link", { name: "Download data as csv" }).click();

      cy.wait("@getDownload")

      cy.get('download-dialog').should('be.visible');
    });
  });
});