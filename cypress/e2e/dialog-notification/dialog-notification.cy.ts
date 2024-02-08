import { datacutWithLinks } from "../../fixtures/datasets";

describe("Dialog notification", () => {
  context("When a user downloads data", () => {
    function visitPageAndDownload() {
      cy.intercept("GET", "**/download.csv", {
        statusCode: 200,
        body: '',
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename=source_link_1.csv'
        }
      }).as("getDownload");

      cy.visit(`/datasets/${datacutWithLinks}`);
      cy.findByRole("link", { name: "Source link 1" }).click();
      cy.findByRole("link", { name: "Download data as CSV" }).click();
      cy.wait("@getDownload")
    }

    it("should show a banner notification", () => {
      visitPageAndDownload();

      cy.findByRole("dialog").should('be.visible');
      cy.findByRole("dialog").within(() => {
        cy.findByText("Important").should("be.visible");
      });
    });

    it("should create a cookie when one does not exist", () => {
      visitPageAndDownload();

      cy.getCookie("notificationLastShown").should("exist");
    });

    it("should not show a banner notification if the cookie exists", () => {
      cy.setCookie("notificationLastShown", "timestampOfCreation");
      visitPageAndDownload();

      cy.findByRole("dialog").should('exist');
      cy.findByRole("dialog").within(() => {
        cy.findByText("Important").should("not.be.visible");
      });
    });

    it("should have a link to the feedback form with a query parameter", () => {
      visitPageAndDownload();

      cy.findByRole("link", { name: "feedback form." }).should(
        "have.attr",
        "href",
        "/feedback?from=csat-link"
      );
    });

    context("When the user clicks the feedback link", () => {
      it("should redirect to the feedback form with analyse data pre-selected", () => {
        visitPageAndDownload();

        cy.findByRole("link", { name: "feedback form." }).click();
        cy.url().should("include", "/feedback/?from=csat-link");

        cy.findByLabelText("Analyse data").should("be.checked");
      });

      it("should show dialog modal and banner notification when user clicks back", () => {
        visitPageAndDownload();

        cy.findByRole("link", { name: "feedback form." }).click();
        cy.findByRole("link", { name: "Back" }).click();

        cy.findByRole("dialog").should('be.visible');
        cy.findByRole("dialog").within(() => {
          cy.findByText("Important").should("be.visible");
        });
      });
    });
  });
});