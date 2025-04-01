import { sourceWithTable } from '../../fixtures/datasets';
import { assertList } from '../../support/assertions';

describe('Unpublish catalogue page', () => {
  it('should display the correct markup', () => {
    cy.visit(`/datasets/${sourceWithTable}/edit-dataset`);
    cy.findByRole('complementary')
      .should('exist')
      .within(() => {
        cy.findByRole('heading', {
          level: 2,
          name: 'Unpublish this catalogue page'
        }).should('have.class', 'govuk-heading-m');

        cy.findByText(
          'Only do this if you suspect a data breach, such as data being extracted or shared incorrectly.'
        ).should('have.class', 'govuk-body');

        cy.findByText('This action will:').should('have.class', 'govuk-body');

        assertList('unpublish-list', [
          'remove the catalogue page from Data Workspace',
          'remove the data from any dashboards or data cuts',
          'revoke access for any users'
        ]);

        cy.get('[data-test="unpublish-catalogue-page"]')
          .should('exist')
          .within(() => {
            cy.findByRole('button', {
              name: 'Unpublish catalogue page'
            }).should('exist');
          });
      });
  });
});
