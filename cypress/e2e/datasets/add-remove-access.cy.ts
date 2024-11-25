import {
  assertDataAccessNotification,
  assertSuccessNotification,
} from "../../support/assertions";

import { sourceWithTableNoAccess } from "../../fixtures/datasets";

describe("Adding and removing access to a dataset", () => {
  context("when I view the manage access page", () => {
    before(() => {
      cy.setUsersEditorAccess(sourceWithTableNoAccess, true);
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
    });
    it("should only show one user that has access", () => {
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
  context("when I search and add a user", () => {
    before(() => {
      cy.setUsersEditorAccess(sourceWithTableNoAccess, true);
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
    });
    it("should show a notification saying an email has been sent and access has been added", () => {
      cy.findByRole("button", { name: "Add users" })
        .should("be.visible")
        .click();
      cy.findByRole("heading", {
        name: "Give a user access to Source dataset - access request",
        level: 1,
      }).should("be.visible");
      cy.findByRole("textbox", {
        name: "Search by email address or name",
      })
        .should("be.visible")
        .type("vyvyan");
      cy.findByRole("button", { name: "Search" }).should("be.visible").click();
      cy.findByText("Found 1 matching user for vyvyan").should("be.visible");
      cy.get("table").within(() => {
        cy.get("tr").should("have.length", 1);
        cy.get("td").contains("Vyvyan Holland");
      });
      cy.findByRole("button", { name: "Add user" })
        .should("be.visible")
        .click();
      assertSuccessNotification(
        "An email has been sent to Vyvyan Holland to let them know they now have access."
      );
    });
  });
  context("when I view the manage access page", () => {
    before(() => {
      cy.setUsersEditorAccess(sourceWithTableNoAccess, true);
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
    });
    it("should show two users that has access", () => {
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
  context("when I remove the users data access", () => {
    beforeEach(() => {
      cy.visit(`datasets/${sourceWithTableNoAccess}/edit-permissions`);
    });
    it("should show a notification saying an email has been sent and access has been removed", () => {
      cy.findByRole("button", {
        name: "Remove user",
      }).click();
      cy.findByRole("dialog").within(() => {
        cy.findByRole("heading", {
          name: "Are you sure you want to remove Vyvyan Holland's access to this data?",
          level: 2,
        }).should("be.visible");
        cy.findByRole("button", {
          name: "Yes, remove user",
        }).click();
      });
      assertSuccessNotification(
        "Vyvyan Holland's access to data has been removed. An email has been sent out to let them know that they no longer have access to the data."
      );
      cy.findByRole("link", {
        name: "View catalogue page",
      })
        .should("be.visible")
        .click();
    });
    it("should only show one user that has access", () => {
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
    it("should display a request access notification to the dataset", () => {
      cy.resetAllPermissions(sourceWithTableNoAccess);
      cy.visit(`datasets/${sourceWithTableNoAccess}`);
      assertDataAccessNotification(sourceWithTableNoAccess);
    });
  });
});
