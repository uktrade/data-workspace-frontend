describe('When clicking I want to add a new dataset', () => {
  context('When clicking Add a new dataset', () => {
    it('should redirect to Adding Data', () => {
      cy.visit('/support-and-feedback/');
      cy.findByRole('radio', {
        name: 'I want to add a new dataset'
      }).click();
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('heading', {
        name: 'Add a new dataset'
      }).should('be.visible');
    });
  });
});
