declare namespace Cypress {
  interface Chainable {
    /**
     * Custom command to select DOM element by data-cy attribute.
     * @example cy.dataCy('greeting')
     */
    setUsersEditorAccess(
      dataSetId: import("./fixtures/datasets").DataCatalogueIDType,
      hasEditorAccess: boolean
    ): Chainable<Element>;

    resetUserPermissions(
      dataSetId: import("./fixtures/datasets").DataCatalogueIDType
    ): Chainable<Element>;

    resetAllPermissions(
      dataSetId: import("./fixtures/datasets").DataCatalogueIDType
    ): Chainable<Element>;
    updateNotificationBanner(
      notificationId: number,
      lastChanceDays: number,
      endDate: string
    ): Chainable<Element>;
  }
}
