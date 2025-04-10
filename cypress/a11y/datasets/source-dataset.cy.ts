import { datacutWithLinks } from '../../fixtures/datasets';

describe('Source dataset catalogue page', () => {
  beforeEach(() => {
    cy.visit(`/datasets/${datacutWithLinks}`);
    cy.injectAxe();
  });

  it('Check entire page for a11y issues', () => {
    cy.checkA11y();
  });
});
