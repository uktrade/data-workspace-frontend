import {
  sourceWithTable,
  sourceWithTableNoPermissions,
} from "../../fixtures/datasets";
import {
  assertTextAndLinks,
  assertDatasetTitle,
  assertTable,
  assertLinksToManageDataset,
  assertDataAccessNotification,
} from "../../support/assertions";

describe("Source dataset catalogue", () => {
  context("when a user has permission to view the dataset", () => {
    beforeEach(() => {
      cy.visit(`/datasets/${sourceWithTable}`);
    });

    it("should display a title", () => {
      assertDatasetTitle("Source dataset", "Source dataset");
    });

    it("should display links to manage the dataset", () => {
      assertLinksToManageDataset({
        "Add to collection": `/collections/select-collection-for-membership/dataset/${sourceWithTable}`,
        "Remove the bookmark from this dataset": `/datasets/${sourceWithTable}/toggle-bookmark`,
        "Report an issue": `mailto:vyvyan.holland@businessandtrade.gov.uk?subject=Reporting an issue - Source dataset a`,
        "Manage dataset": `/datasets/${sourceWithTable}}/edit-dataset`,
        "Manage editors": `/datasets/${sourceWithTable}}/edit-data-catalogue-editors`,
      });
    });

    it("should have a summary section", () => {
      assertTextAndLinks("dataset-summary", [
        { text: "Summary" },
        { text: "This is a short description about a source dataset" },
        { text: "Personal data" },
        { text: "Does not contain personal data" },
        { text: "Usage restrictions" },
        { text: "DBT internal use only" },
        { text: "Date added" },
        { text: "12 January 2024" },
        { text: "Update frequency" },
        { text: "Daily" },
        { text: "Publisher" },
        { text: "Source" },
        { text: "Contact" },
        {
          text: "vyvyan.holland@businessandtrade.gov.uk",
          link: "mailto:vyvyan.holland@businessandtrade.gov.uk",
        },
      ]);
    });

    it("should NOT display a notification for requesting access to the data", () => {
      cy.findByTestId("request-access-to-data").should("not.exist");
    });

    it("should display a data table", () => {
      cy.findByRole("heading", { level: 2, name: "Data tables" });
      assertTable({
        headers: ["Name", "Table name", "Last updated"],
        rows: [
          [
            {
              text: "Source data set",
            },
            {
              text: "public.test_dataset",
            },
            {
              text: "N/A, N/A",
            },
          ],
        ],
      });
    });

    it("should display a governance summary", () => {
      cy.findByRole("heading", { level: 2, name: "Governance" });
      assertTextAndLinks("governance-summary", [
        { text: "Information Asset Manager (IAM)" },
        {
          text: "Find out more about IAM's",
          link: "https://workspace.trade.gov.uk/working-at-dbt/policies-and-guidance/guidance/information-assets/#information-asset-managers-iams",
        },
        {
          text: "Bob Testerson",
          link: "mailto:bob.testerson@example.com",
        },
        {
          text: "Information Asset Owner (IAO)",
        },
        {
          text: "Find out more about IAO's",
          link: "https://workspace.trade.gov.uk/working-at-dbt/policies-and-guidance/guidance/information-assets/#information-asset-owners-iaos",
        },
        {
          text: "Vyvyan Holland",
          link: "mailto:vyvyan.holland@businessandtrade.gov.uk",
        },
        {
          text: "No licence",
          link: "http://some-url.com",
        },
        {
          text: "Retention period details",
        },
        {
          text: "Records are retained for 10 years after the form was submitted",
        },
      ]);
    });

    it("should display data usage", () => {
      cy.findByRole("heading", { level: 2, name: "Data usage" });
      assertTextAndLinks("data-usage", [
        {
          text: "The data below has been captured since this catalogue item was initially published.",
        },
      ]);
    });

    it("should not display any related dashboards", () => {
      cy.findByRole("heading", { level: 2, name: "Related dashboards" });
      assertTextAndLinks("related-dashboards", [
        {
          text: "This data currently has no related dashboards.",
        },
        {
          text: "If you'd like to create a dashboard using this data then you can see",
        },
        {
          text: "how to create a dashboard with Quicksight.",
          link: "https://data-services-help.trade.gov.uk/data-workspace/how-to/see-tools-specific-guidance/quicksight/create-a-dashboard/",
        },
      ]);
    });
  });

  context("when a user has NO permissions to view the dataset", () => {
    beforeEach(() => {
      cy.visit(`/datasets/${sourceWithTableNoPermissions}`);
    });

    it("should display a title", () => {
      assertDatasetTitle("Source dataset", "source dataset - no permissions");
    });

    it("should display links to manage the dataset", () => {
      assertLinksToManageDataset({
        "Add to collection": `/collections/select-collection-for-membership/dataset/${sourceWithTableNoPermissions}`,
        "Bookmark this dataset": `/datasets/${sourceWithTableNoPermissions}/toggle-bookmark`,
        "Report an issue": `mailto:vyvyan.holland@businessandtrade.gov.uk?subject=Reporting an issue - Source dataset a`,
      });
    });

    it("should have a summary section", () => {
      assertTextAndLinks("dataset-summary", [
        { text: "Summary" },
        { text: "This is a short description about a source dataset" },
        { text: "Personal data" },
        { text: "Does not contain personal data" },
        { text: "Usage restrictions" },
        { text: "DBT internal use only" },
        { text: "Date added" },
        { text: "12 January 2024" },
        { text: "Update frequency" },
        { text: "Daily" },
        { text: "Publisher" },
        { text: "Source" },
        { text: "Contact" },
        {
          text: "vyvyan.holland@businessandtrade.gov.uk",
          link: "mailto:vyvyan.holland@businessandtrade.gov.uk",
        },
      ]);
    });

    it("should display a notification for requesting access to the data", () => {
      assertDataAccessNotification(sourceWithTableNoPermissions);
    });

    it("should display a data table", () => {
      cy.findByRole("heading", { level: 2, name: "Data tables" });
      assertTable({
        headers: ["Name", "Table name", "Last updated"],
        rows: [
          [
            {
              text: "Source data set",
            },
            {
              text: "public.test_dataset",
            },
            {
              text: "N/A, N/A",
            },
          ],
        ],
      });
    });

    it("should display a governance summary", () => {
      cy.findByRole("heading", { level: 2, name: "Governance" });
      assertTextAndLinks("governance-summary", [
        { text: "Information Asset Manager (IAM)" },
        {
          text: "Find out more about IAM's",
          link: "https://workspace.trade.gov.uk/working-at-dbt/policies-and-guidance/guidance/information-assets/#information-asset-managers-iams",
        },
        {
          text: "Bob Testerson",
          link: "mailto:bob.testerson@example.com",
        },
        {
          text: "Information Asset Owner (IAO)",
        },
        {
          text: "Find out more about IAO's",
          link: "https://workspace.trade.gov.uk/working-at-dbt/policies-and-guidance/guidance/information-assets/#information-asset-owners-iaos",
        },
        {
          text: "Bob Testerson",
          link: "mailto:bob.testerson@example.com",
        },
        {
          text: "No licence",
          link: "http://some-url.com",
        },
        {
          text: "Retention period details",
        },
        {
          text: "Records are retained for 10 years after the form was submitted",
        },
      ]);
    });

    it("should display data usage", () => {
      cy.findByRole("heading", { level: 2, name: "Data usage" });
      assertTextAndLinks("data-usage", [
        {
          text: "The data below has been captured since this catalogue item was initially published.",
        },
      ]);
    });

    it("should not display any related dashboards", () => {
      cy.findByRole("heading", { level: 2, name: "Related dashboards" });
      assertTextAndLinks("related-dashboards", [
        {
          text: "This data currently has no related dashboards.",
        },
        {
          text: "If you'd like to create a dashboard using this data then you can see",
        },
        {
          text: "how to create a dashboard with Quicksight.",
          link: "https://data-services-help.trade.gov.uk/data-workspace/how-to/see-tools-specific-guidance/quicksight/create-a-dashboard/",
        },
      ]);
    });
  });
});
