declare namespace Cypress {
  interface Chainable {
    /**
     * Custom command to select DOM element by data-cy attribute.
     * @example cy.dataCy('greeting')
     */
    setUsersEditorAccess(
      dataSetId: string,
      hasEditorAccess: boolean
    ): Chainable<Element>;
  }
}
