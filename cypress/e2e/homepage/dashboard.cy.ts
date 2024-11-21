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
      }).should("be.visible");
    });

    it("should show a 'Get help' article", () => {
      cy.findByRole("heading", {
        level: 3,
        name: "Get help",
      }).should("be.visible");
      cy.findByRole("heading", {
        level: 4,
        name: "Suggested articles",
      }).should("be.visible");
    });

    it("should show a 'Get in touch' article", () => {
      cy.findByRole("heading", {
        level: 3,
        name: "Get in touch",
      }).should("be.visible");
      ["Message", "Community", "Work"].forEach((message) => {
        cy.findByRole("heading", {
          level: 4,
          name: message,
        }).should("be.visible");
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
      }).should("be.visible");
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
      }).should("be.visible");
      cy.findByRole("link", { name: "Create a collection" }).should(
        "be.visible"
      );
      cy.findByRole("link", {
        name: "Find out more about collections",
      }).should("be.visible");
      cy.findByRole("link", {
        name: "Personal collection a",
      }).should("not.exist");
    });

    it("should show the 'Your recent tools' section with NO tools", () => {
      cy.wait("@recentTools");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent tools",
      }).should("be.visible");
      cy.findByRole("link", { name: "Visit tools" }).should("be.visible");
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
      }).should("be.visible");
      cy.findByRole("link", { name: "Data cut - links" }).should("not.exist");
      cy.findByRole("link", { name: "View all bookmarks" }).should("not.exist");
    });
  });

  context("When an exisiting user visits the page", () => {
    beforeEach(() => {
      cy.intercept(endpoints.recentItems, {
        results: [
          {
            id: 1,
            timestamp: "2024-11-14T13:20:56.068509Z",
            event_type: "Dataset view",
            user_id: 2,
            related_object: {
              id: "1234",
              type: "Source dataset",
              name: "Some source dataset",
            },
            extra: {
              path: "/datasets/1234",
            },
          },
        ],
      }).as("recentItems");
      cy.intercept(endpoints.recentCollections, {
        results: [
          {
            name: "Ian's source data set",
            datasets: [],
            visualisation_catalogue_items: [],
            collection_url: "/collections/1234",
          },
        ],
      }).as("recentCollections");
      cy.intercept(endpoints.recentTools, {
        results: [
          {
            id: 1,
            extra: {
              tool: "Data Explorer",
            },
            tool_url: "/tools/explorer/redirect",
          },
          {
            id: 2,
            extra: {
              tool: "Superset",
            },
            tool_url: "/tools/superset/redirect",
          },
        ],
      }).as("recentTools");
      cy.intercept(endpoints.yourBookmarks, {
        results: [
          {
            id: "1234",
            name: "Some bookmarked dataset",
            url: "/datasets/1234",
            created: "2023-12-18T15:22:42.860061Z",
          },
        ],
      }).as("yourBookmarks");
      cy.visit("/");
    });

    it("should show the 'Your recent items' section with items", () => {
      cy.wait("@recentItems");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent items",
      }).should("be.visible");
      cy.findByRole("link", { name: "Some source dataset" }).should(
        "be.visible"
      );
      cy.findByRole("link", { name: "Data types on Data Workspace" }).should(
        "not.exist"
      );
    });

    it("should show the 'Your recent collections' section with collections", () => {
      cy.wait("@recentCollections");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent collections",
      }).should("be.visible");
      cy.findByRole("link", { name: "Create a collection" }).should(
        "not.exist"
      );
      cy.findAllByRole("link", {
        name: "Find out more about collections",
      }).should("not.exist");
      cy.findAllByRole("link", {
        name: "Ian's source data set",
      }).should("be.visible");
    });

    it("should show the 'Your recent tools' section with tools", () => {
      cy.wait("@recentTools");
      cy.findByRole("heading", {
        level: 2,
        name: "Your recent tools",
      }).should("be.visible");
      cy.findAllByRole("link", { name: "Visit tools" }).should("not.exist");
      cy.findAllByRole("link", { name: "Find out more about tools" }).should(
        "not.exist"
      );
      cy.findByRole("link", { name: "Superset" }).should("be.visible");
    });

    it("should show the 'Your bookmarks' section with bookmarks", () => {
      cy.wait("@yourBookmarks");
      cy.findByRole("heading", {
        level: 2,
        name: "Your bookmarks",
      }).should("be.visible");
      cy.findByTestId("your-bookmarks").within(($form) => {
        cy.findByRole("link", { name: "Some bookmarked dataset" }).should(
          "exist"
        );
      });
      cy.findByRole("link", { name: "View all bookmarks" }).should(
        "be.visible"
      );
    });
  });
});
