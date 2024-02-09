const endpoints = {
  recentItems: "/api/v2/recent_items/*",
  recentCollections: "/api/v2/collections/*",
  recentTools: "/api/v2/recent_tools/*",
  yourBookmarks: "/api/v2/your_bookmarks/*",
} as const;

describe("Homepage dashboard", () => {
  context("When any user visits the page", () => {
    beforeEach(() => {
      cy.visit("/");
    });

    it("should show a support title", () => {
      cy.findByRole("heading", {
        level: 2,
        name: "How we can support you",
      }).should("exist");
    });

    it("should show a 'Get help' article", () => {
      cy.findByRole("heading", {
        level: 3,
        name: "Get help",
      }).should("exist");
      cy.findByRole("heading", {
        level: 4,
        name: "Suggested articles",
      }).should("exist");
    });

    it("should show a 'Get in touch' article", () => {
      cy.findByRole("heading", {
        level: 3,
        name: "Get in touch",
      }).should("exist");
      ["Message", "Community", "Work"].forEach((message) => {
        cy.findByRole("heading", {
          level: 4,
          name: message,
        }).should("exist");
      });
    });
  });

  context("When a user visits the page for the first time", () => {
    beforeEach(() => {
      cy.intercept(endpoints.recentItems, { results: [] }).as("recentItems");
      cy.intercept(endpoints.recentCollections, { results: [] }).as(
        "recentCollections"
      );
      cy.intercept(endpoints.recentTools, { results: [] }).as("recentTools");
      cy.intercept(endpoints.yourBookmarks, { results: [] }).as(
        "yourBookmarks"
      );
      cy.visit("/");
    });

    it("should show the 'Your recent items' section with NO items", () => {
      cy.wait("@recentItems");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent items",
      }).should("exist");
      cy.findByRole("link", { name: "Data cut - links" }).should("not.exist");
      cy.findByRole("link", { name: "Data types on Data Workspace" }).should(
        "exist"
      );
      cy.findByRole("link", { name: "Data cut - links" }).should("not.exist");
    });

    it("should show the 'Your recent collections' section with NO collections", () => {
      cy.wait("@recentCollections");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent collections",
      }).should("exist");
      cy.findByRole("link", { name: "Create a collection" }).should("exist");
      cy.findByRole("link", {
        name: "Find out more about collections",
      }).should("exist");
      cy.findByRole("link", {
        name: "Collection a",
      }).should("not.exist");
    });

    it("should show the 'Your recent tools' section with NO tools", () => {
      cy.wait("@recentTools");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent tools",
      }).should("exist");
      cy.findByRole("link", { name: "Visit tools" }).should("exist");
      cy.findByRole("link", { name: "Find out more about tools" }).should(
        "exist"
      );
      cy.findByRole("link", { name: "Superset" }).should("not.exist");
    });

    it("should show the 'Your bookmarks' section with NO bookmarks", () => {
      cy.wait("@yourBookmarks");
      cy.findByRole("heading", {
        level: 2,
        name: "Your bookmarks",
      }).should("exist");
      cy.findByRole("link", { name: "Data cut - links" }).should("not.exist");
      cy.findByRole("link", { name: "View all bookmarks" }).should("not.exist");
    });
  });

  context("When an exisiting user visits the page", () => {
    beforeEach(() => {
      cy.intercept(endpoints.recentItems).as("recentItems");
      cy.intercept(endpoints.recentCollections).as("recentCollections");
      cy.intercept(endpoints.recentTools).as("recentTools");
      cy.intercept(endpoints.yourBookmarks).as("yourBookmarks");
      cy.visit("/");
    });

    it("should show the 'Your recent items' section with items", () => {
      cy.wait("@recentItems");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent items",
      }).should("exist");
      cy.findByRole("link", { name: "Data cut - links" }).should("exist");
      cy.findByRole("link", { name: "Data types on Data Workspace" }).should(
        "not.exist"
      );
    });

    it("should show the 'Your recent collections' section with collections", () => {
      cy.wait("@recentCollections");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent collections",
      }).should("exist");
      cy.findByRole("link", { name: "Create a collection" }).should(
        "not.exist"
      );
      cy.findAllByRole("link", {
        name: "Find out more about collections",
      }).should("not.exist");
      cy.findAllByRole("link", {
        name: "Collection a",
      }).should("exist");
    });

    it("should show the 'Your recent tools' section with tools", () => {
      cy.wait("@recentTools");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent tools",
      }).should("exist");
      cy.findAllByRole("link", { name: "Visit tools" }).should("not.exist");
      cy.findAllByRole("link", { name: "Find out more about tools" }).should(
        "not.exist"
      );
      cy.findByRole("link", { name: "Superset" }).should("exist");
    });

    it.only("should show the 'Your bookmarks' section with bookmarks", () => {
      cy.wait("@yourBookmarks");
      cy.findByRole("heading", {
        level: 2,
        name: "Your bookmarks",
      }).should("exist");
      cy.findByRole("link", { name: "Source dataset a" }).should("exist");
      cy.findByRole("link", { name: "View all bookmarks" }).should("exist");
    });
  });
});
