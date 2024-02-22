import type { DataCatalogueIDType } from "../fixtures/datasets";

type assertTableType = {
  headers: string[];
  rows: [
    {
      text: string;
      link?: string;
    }[]
  ];
};

type assertTextandLinksType = {
  text: string;
  link?: string;
}[];

const assertDatasetTitle = (subtitle: string, title: string) => {
  cy.findAllByText(subtitle).should("exist");
  cy.findByRole("heading", { level: 1, name: title });
};

const assertLinksToManageDataset = (titleAndLinks: Record<string, string>) => {
  for (const [title, href] of Object.entries(titleAndLinks)) {
    cy.findByRole("link", { name: title });
  }
};

const assertTextAndLinks = (
  selector: string,
  content: assertTextandLinksType
) => {
  cy.findByTestId(selector).within(() => {
    content.forEach((item) => {
      if (item.link) {
        cy.findAllByRole("link", { name: item.text }).should(
          "have.attr",
          "href",
          item.link
        );
      } else {
        cy.findByText(item.text).should("be.visible");
      }
    });
  });
};

const assertTable = (table: assertTableType) => {
  cy.get("table").within(() => {
    const { headers, rows } = table;

    headers.forEach((header, index) => {
      cy.get("th").eq(index).contains(header);
    });

    rows.forEach((row) => {
      row.forEach((cell, index) => {
        cy.get("td").eq(index).contains(cell.text);
        if (cell.link) {
          cy.get("td")
            .eq(index)
            .find("a")
            .should("have.attr", "href", cell.link);
        }
      });
    });
  });
};

const assertDataAccessNotification = (id: DataCatalogueIDType) => {
  cy.findByTestId("request-access-to-data").within(() => {
    cy.findByText(
      "Access to this data is restricted. To find out why check the usage restrictions. You can view the table structure but not the data itself."
    );
  });
  cy.findByRole("link", { name: "Request access to data" }).should(
    "have.attr",
    "href",
    `/request-access/${id}`
  );
};

export {
  assertTable,
  assertTextAndLinks,
  assertDatasetTitle,
  assertLinksToManageDataset,
  assertDataAccessNotification,
};
