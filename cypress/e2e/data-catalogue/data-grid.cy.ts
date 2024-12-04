import { sourceWithTable } from "../../fixtures/datasets";

const dataUrl = "**/data?count=1";

const checkRequestBody = (alias: string, expected: string) => {
  cy.wait(alias)
    .its("request.body")
    .then((body) => JSON.stringify(body))
    .should("include", expected);
};

describe("Data grid filters", () => {
  context("When filtering a boolean column", () => {
    it("should clear the filter when reset view is clicked", () => {
      cy.visit(`/datasets/${sourceWithTable}`);

      cy.intercept("POST", dataUrl, {
        statusCode: 200,
        body: {
          rowcount: {
            count: 3,
          },
          download_limit: 100,
          records: [
            {
              id: 1,
              data: true,
            },
            {
              id: 2,
              data: false,
            },
            {
              id: 3,
              data: true,
            },
          ],
        },
      }).as("getData");
      cy.get("a").contains("source data set").click();
      checkRequestBody("@getData", '"filters":{}');
      cy.get("span.ag-icon.ag-icon-menu").last().click();

      cy.intercept("POST", dataUrl).as("filteredData");
      cy.get('input[aria-label="Filter Value"]').type("true");
      checkRequestBody("@filteredData", '"filter":"true"');

      cy.intercept("POST", dataUrl).as("resetData");
      cy.get("button").contains("Reset view").click();
      checkRequestBody("@resetData", '"filters":{}');
    });
  });
});
