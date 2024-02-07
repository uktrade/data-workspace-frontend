import { datacutWithLinks } from "../../fixtures/datasets";
export const endpoints = {
  recentItems: "/api/v2/recent_items/*",
  recentCollections: "/api/v2/collections/*",
  recentTools: "/api/v2/recent_tools/*",
  yourBookmarks: "/api/v2/your_bookmarks/*",
} as const;

const assertEndPointIsNotCalled = (pathnameToAssert: string): void => {
  cy.get("@GET.all").then((XHRRequests) => {
    XHRRequests.map(({ request: { url } }) => {
      const { pathname } = new URL(url);
      expect(pathname).not.equal(pathnameToAssert);
    });
  });
};

describe("Homepage search", () => {
  beforeEach(() => {
    cy.intercept({ method: "GET", path: "*" }).as("GET");
    cy.intercept(endpoints.recentItems, { results: [] });
    cy.intercept(endpoints.recentCollections, { results: [] });
    cy.intercept(endpoints.recentTools, { results: [] });
    cy.intercept(endpoints.yourBookmarks, { results: [] });
    cy.intercept("/find_suggested_searches?query=data", [
      {
        name: "Data cut - links",
        type: "",
        url: "",
      },
    ]);
    cy.visit("/");
    cy.findByTestId("search-input").find("input").as("searchInputField");
    cy.findByTestId("search-input").next("input").as("searchButton");
  });

  it("should show a search bar with a link to getting started", () => {
    cy.findByRole("heading", {
      level: 1,
      name: "Search Data Workspace",
    })
      .parent()
      .findByRole("link", { name: "Getting started as a new user" })
      .should("have.attr", "href", "/welcome");
  });

  context("when a user visits the first time", () => {
    it("should NOT show search suggestions on page load", () => {
      cy.findByRole("heading", { level: 3, name: "Suggested searches" }).should(
        "not.exist"
      );
    });

    it("should NOT call the suggested search endpoint when a query param is present", () => {
      cy.visit("/?q=data");
      assertEndPointIsNotCalled("/datasets/find_suggested_searches");
    });
  });

  context("when a user searches for a dataset", () => {
    it("should persist the search query to the data catalogue page and NOT show suggested searches", () => {
      cy.get("@searchInputField").type("Data cut - links");
      cy.get("@searchButton").click();
      cy.get("@searchInputField").should("have.value", "Data cut - links");
      cy.findByRole("heading", { level: 3, name: "Suggested searches" }).should(
        "not.exist"
      );
    });
  });
  context("when a user revisits the homepage after viewing a dataset", () => {
    it("should show suggested searches when typing", () => {
      cy.visit(`/datasets/${datacutWithLinks}`);
      cy.visit("/");
      cy.get("@searchInputField").type("Data");
      cy.findByRole("heading", { level: 3, name: "Suggested searches" }).should(
        "exist"
      );
    });
  });
});
