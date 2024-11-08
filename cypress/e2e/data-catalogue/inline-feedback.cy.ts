const positiveChoices = [
  'I found the information I needed',
  'It was easy to find relevant datasets',
  'The filters helped me narrow down my search results',
  'It was easy to determine what datasets could be useful',
  'Other'
];

const negativeChoices = [
  'I did not find the information I needed',
  'It was hard to find relevant datasets',
  'The filters did not help me find relevant datasets',
  'It was hard to determine what datasets could be useful',
  'Other'
];

const assertPayload = (wasItHelpful: boolean) => {
  cy.wait('@postInline').its('request.body').should('include', {
    was_this_page_helpful: wasItHelpful,
    location: 'data-catalogue'
  });
};

const assertAdditionalForm = (
  wasItHelpful: 'Yes' | 'No',
  choices: string[]
) => {
  cy.findByRole('button', { name: wasItHelpful }).click();
  wasItHelpful == 'Yes' ? assertPayload(true) : assertPayload(false);
  cy.findByRole('heading', {
    name: 'Thanks for letting us know, your response has been recorded.',
    level: 2
  });
  cy.findByRole('group', {
    name:
      wasItHelpful == 'Yes'
        ? 'Tell us more about why this page was helpful (optional)'
        : 'Tell us more about your experience (optional)'
  });

  choices.forEach((name) => {
    cy.findByRole('checkbox', { name });
  });

  cy.findByRole('textbox', {
    name:
      wasItHelpful == 'Yes'
        ? 'Is there anything else you can tell us? (optional)'
        : 'Help us improve this page by giving more detail (optional)'
  });

  cy.findByRole('button', { name: 'Send ' });
  cy.findByRole('link', { name: 'Cancel' });
};

describe('Data catalogue inline ', () => {
  beforeEach(() => {
    cy.visit('/datasets/');
    cy.intercept({
      method: 'POST',
      url: '/api/v2/inline_'
    }).as('postInline');
    cy.intercept({
      method: 'PATCH',
      url: '/api/v2/inline_/*'
    }).as('patchAdditonal');
  });

  context('when a user visits the data catalogue page', () => {
    beforeEach(() => {
      cy.visit('/datasets/');
    });

    it('should display an inline  form', () => {
      cy.findByRole('heading', {
        level: 2,
        name: 'Was this page helpful?'
      }).should('exist');
      cy.findByRole('button', { name: 'Yes' });
      cy.findByRole('button', { name: 'No' });
    });
  });

  context('when a user clicks Yes', () => {
    it('should display an additional form with more options', () => {
      assertAdditionalForm('Yes', positiveChoices);
    });
  });

  context('when a user clicks No', () => {
    it('should display an additional form with more options', () => {
      assertAdditionalForm('No', negativeChoices);
    });
  });

  context('when a user submits additional positive ', () => {
    it('should update the original  post with more data', () => {
      cy.findByRole('button', { name: 'Yes' }).click();
      cy.wait('@postInline').then((interception) => {
        const id = interception.response.body.id;
        positiveChoices.forEach((name) => {
          cy.findByRole('checkbox', { name }).click();
        });

        cy.findByRole('textbox', {
          name: 'Is there anything else you can tell us? (optional)'
        }).type('This page is fantastic');
        cy.findByRole('button', { name: 'Send ' }).click();
        cy.wait('@patchAdditonal')
          .its('response.body')
          .should('include', {
            id: id,
            location: 'data-catalogue',
            was_this_page_helpful: true,
            inline__choices: positiveChoices.join(','),
            more_detail: 'This page is fantastic'
          });
        cy.findByRole('group', {
          name: 'Tell us more about why this page was helpful (optional)'
        }).should('not.exist');
      });
    });
  });

  context('when a user submits additional negative ', () => {
    it('should update the original  post with more data', () => {
      cy.findByRole('button', { name: 'No' }).click();
      cy.wait('@postInline').then((interception) => {
        const id = interception.response.body.id;
        negativeChoices.forEach((name) => {
          cy.findByRole('checkbox', { name }).click();
        });
        cy.findByRole('textbox', {
          name: 'Help us improve this page by giving more detail (optional)'
        }).type('This page is not so great');
        cy.findByRole('button', { name: 'Send ' }).click();
        cy.wait('@patchAdditonal')
          .its('response.body')
          .should('include', {
            id: id,
            location: 'data-catalogue',
            was_this_page_helpful: false,
            inline__choices: negativeChoices.join(','),
            more_detail: 'This page is not so great'
          });
        cy.findByRole('group', {
          name: 'Tell us more about your experience (optional)'
        }).should('not.exist');
      });
    });
  });
  
  context('when a user resets the form', () => {
    it('should hide the addtional form', () => {
      cy.findByTestId('additional-').should('not.exist');
      cy.findByRole('button', { name: 'Yes' }).click();
      cy.findByTestId('additional-').should('exist');
      cy.findByRole('link', { name: 'Cancel' }).click();
      cy.findByTestId('additional-').should('not.exist');
    });
  });
});
