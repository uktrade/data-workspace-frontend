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

  it('should display a dialog with content and buttons', () => {
    cy.visit(`/datasets/${sourceWithTable}/edit-dataset`);
    cy.get('[data-test="unpublish-catalogue-page"]')
      .contains('button', 'Unpublish catalogue page')
      .click();
    cy.getOpenDialog().within(() => {
      cy.contains('strong', 'Final review before unpublishing').should('exist');
      cy.contains(
        "By clicking the 'Yes' button below you're confirmimg:"
      ).should('exist');
      cy.contains(
        'this catalogue page needs to be unpublished because of a potential data breach'
      ).should('exist');
      cy.contains(
        'you understand that any data linked to this catalogue page will also be removed'
      ).should('exist');
      cy.contains('button', 'Yes, unpublish catalogue page').should('exist');
      cy.contains('button', 'Close').should('exist');
    });
  });
});
