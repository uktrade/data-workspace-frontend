/* eslint-disable no-undef */
/* eslint-disable prettier/prettier */

const expectedSummaryAnswers = {
  'What is the name of the dataset?': 'Name',
  'Summarise this dataset': 'Test summarise this dataset',
  'Describe this dataset': 'Test describe this dataset',
  'Name of Information Asset Owner (IAO)':
    'vyvyan.holland@businessandtrade.gov.uk',
  'Name of Information Asset Manager (IAM)':
    'vyvyan.holland@businessandtrade.gov.uk',
  'Contact person': 'vyvyan.holland@businessandtrade.gov.uk',
  'Do you need/have a licence for this data?': 'no'
};
describe('Requesting a dataset', () => {
  context('When clicking Add a new dataset', () => {
    it('should redirect to Adding Data', () => {
      cy.visit('/support-and-feedback/');
      cy.findByRole('radio', {
        name: 'I want to add a new dataset'
      }).click();
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('heading', {
        name: 'Adding data'
      }).should('be.visible');
      cy.findByRole('button', { name: 'Add new catalogue item' }).click();
      cy.findByRole('heading', {
        name: 'Add a new dataset'
      }).should('be.visible');
      cy.findByRole('button', { name: 'Start' }).click();
      cy.findByRole('link', { name: 'Summary information' }).click();
      cy.findByText('Step 1 of 7').should('be.visible');
      cy.findByRole('heading', {
        name: 'What is the name of the dataset?'
      }).should('be.visible');
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('link', {
        name: 'This field is required.'
      }).should('be.visible');
      cy.findByRole('textbox', {
        name: 'What is the name of the dataset?'
      }).type('Name');
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('textbox', {
        name: 'Summarise this dataset'
      }).type('Test summarise this dataset');
      cy.findByRole('textbox', {
        name: 'Describe this dataset'
      }).type('Test describe this dataset');
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('link', {
        name: 'The description must be minimum 30 words'
      }).should('be.visible');
      cy.findByRole('textbox', {
        name: 'Describe this dataset'
      }).type(
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum auctor convallis neque et hendrerit. Suspendisse sit amet vulputate purus. Phasellus tristique luctus arcu, quis viverra mi eleifend et. Vestibulum suscipit.'
      );
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('link', {
        name: 'Find out more information about data owner roles and responsibilities'
      }).should('be.visible');
      cy.findByRole('heading', {
        name: 'Name of Information Asset Owner (IAO)'
      }).should('be.visible');
      cy.findByRole('textbox', {
        name: 'Search by email address or name'
      }).type('vyvyan');
      cy.findByRole('button', { name: 'Search' }).click();

      cy.findByRole('button', { name: 'Add' }).click();
      cy.findByRole('heading', {
        name: 'Name of Information Asset Manager (IAM)'
      }).should('be.visible');
      cy.findByRole('textbox', {
        name: 'Search by email address or name'
      }).type('vyvyan');
      cy.findByRole('button', { name: 'Search' }).click();
      cy.findByRole('button', { name: 'Add' }).click();
      cy.findByRole('heading', {
        name: 'Contact person'
      }).should('be.visible');
      cy.findByRole('textbox', {
        name: 'Search by email address or name'
      }).type('vyvyan');
      cy.findByRole('button', { name: 'Search' }).click();
      cy.findByRole('button', { name: 'Add' }).click();
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('link', {
        name: 'This field is required.'
      }).should('be.visible');
      cy.findByRole('radio', {
        name: 'No'
      }).click();
      cy.findByRole('button', { name: 'Continue' }).click();
      cy.findByRole('heading', {
        name: 'Your answers'
      }).should('be.visible');
      Object.entries(expectedSummaryAnswers).forEach(([question, answer]) => {
        cy.findByText(question)
          .should('exist')
          .next()
          .should('contains.text', answer);
      });
    });
  });
});
