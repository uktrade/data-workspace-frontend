describe('Collections page', () => {
  beforeEach(() => {
    cy.visit('/collections');
    cy.injectAxe();
  });

  it('Check entire page for a11y issues', () => {
    cy.checkA11y();
  });
});
