import { sourceWithTableNoAccess } from "../../fixtures/datasets";
import { assertSuccessNotification } from "../../support/assertions";

describe("Requesting data access", () => {
  context("when I request access to this dataset", () => {
    beforeEach(() => {
      cy.setUsersEditorAccess(sourceWithTableNoAccess, false);
      cy.visit(`/datasets/${sourceWithTableNoAccess}`);
      cy.findByRole("link", { name: "Request access to data" }).click();
    });
    it("should display an error message when I don't enter a reason", () => {
      cy.findByRole("heading", {
        name: "Request access to data",
        level: 1,
      }).should("be.visible");
      cy.get("form")
        .findByRole("textbox", {
          name: "Contact email",
        })
        .should("have.attr", "value", "vyvyan.holland@businessandtrade.gov.uk");

      cy.get("form").findByRole("button").click();
      cy.findByRole("alert").within(() => {
        cy.findByRole("heading", {
          name: "There is a problem",
          level: 2,
        }).should("be.visible");
        cy.findByRole("link", {
          name: "Enter a reason for requesting this data.",
        }).should("be.visible");
      });
    });
    it("should summarize your request when you correctly fill out the form", () => {
      cy.get("form")
        .findByRole("textbox", {
          name: "Why do you need this data?",
        })
        .type("I need it");
      cy.get("form").findByRole("button").click();
      cy.findByRole("heading", {
        name: "Check your answers before sending your request",
        level: 1,
      }).should("be.visible");
      cy.findByText("Contact email")
        .should("be.visible")
        .next("dd")
        .findByText("vyvyan.holland@businessandtrade.gov.uk")
        .should("be.visible");

      cy.findByText("Reason to access this data")
        .should("be.visible")
        .next("dd")
        .findByText("I need it")
        .should("be.visible");
      cy.get("form").findByRole("button", { name: "Submit" }).click();

      cy.findByRole("heading", {
        name: "Request received",
        level: 1,
      }).should("be.visible");

      cy.findByText("You've requested access to")
        .should("be.visible")
        .findByRole("link", { name: "Source dataset - access request." })
        .should("be.visible")
        .should(
          "have.attr",
          "href",
          `/datasets/${sourceWithTableNoAccess}`
        );
    });
  });
});

describe("Approving and denying the data access request", () => {
  context("when I review the access request and deny access", () => {
    before(() => {
      cy.setUsersEditorAccess(sourceWithTableNoAccess, true);
      cy.visit(`/datasets/${sourceWithTableNoAccess}/review-access/2`);
    });
    it("should confirm that the request has been denied", () => {
      cy.findByRole("radio", {
        name: "Deny Vyvyan Holland access to this dataset",
      }).click();
      cy.findByRole("textbox", {
        name: "Why are you denying access to this data?",
      }).type("Sorry you are not allowed");
      cy.get("form").findByRole("button", { name: "Submit" }).click();
      assertSuccessNotification(
        "An email has been sent to Vyvyan Holland to let them know their access request was not successful."
      );
    });

    it("should only display the IAO user", () => {
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
      cy.findByRole("heading", {
        name: "Manage access to Source dataset - access request",
        level: 1,
      }).should("be.visible");
      cy.findByRole("heading", {
        name: "Users who have access",
        level: 2,
      }).should("be.visible");
      cy.get("table").within(() => {
        cy.get("tr").should("have.length", 1);
        cy.get("td").contains("Bob Testerson (Information Asset Manager)");
      });
    });
  });
  context("when I review the access request and approve access", () => {
    before(() => {
      cy.visit(`/datasets/${sourceWithTableNoAccess}/review-access/2`);
    });
    after(() => {
      cy.resetUserPermissions(sourceWithTableNoAccess);
    });
    it("should confirm that the request has been approved", () => {
      cy.findByRole("radio", {
        name: "Grant Vyvyan Holland access to this dataset",
      }).click();
      cy.get("form").findByRole("button", { name: "Submit" }).click();
      assertSuccessNotification(
        "An email has been sent to Vyvyan Holland to let them know they now have access."
      );
    });
    it("should NOT display a notification for requesting access to the dataset", () => {
      cy.visit(`/datasets/${sourceWithTableNoAccess}`);
      cy.findAllByTestId("request-access-to-data").should("not.exist");
    });
    it("should display two users who have access", () => {
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
      cy.findByRole("heading", {
        name: "Manage access to Source dataset - access request",
        level: 1,
      }).should("be.visible");

      cy.findByRole("heading", {
        name: "Users who have access",
        level: 2,
      }).should("be.visible");
      cy.get("table").within(() => {
        cy.get("tr").should("have.length", 2);
        cy.get("td").contains("Bob Testerson (Information Asset Manager)");
        cy.get("td").contains("Vyvyan Holland");
      });
    });
  });
});
