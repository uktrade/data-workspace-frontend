const setCertificateDate = (day: string, month: string, year: string) => {
  cy.findByRole('textbox', {
    name: 'Day'
  }).type(day);
  cy.findByRole('textbox', {
    name: 'Month'
  }).type(month);
  cy.findByRole('textbox', {
    name: 'Year'
  }).type(year);
};

const acceptDeclaration = () => {
  cy.findByRole('checkbox').click();
};

const assertErrorMessages = (messages: string[]) => {
  messages.forEach((message) => {
    cy.findByRole('alert')
      .within(() =>
        cy.findByRole('link', {
          name: message
        })
      )
      .should('be.visible');
    cy.findByRole('group', {
      name: 'Enter the date that\'s on your certificate'
    }).within(() => cy.findByText(message).should('be.visible'));
  });
};

describe('Self certify tools access', () => {
  context('when a user goes to access tools', () => {
    it('should NOT be able to access tools', () => {
      cy.visit('/tools');
      cy.findByRole('alert').should('not.exist');
      [
        'Get access to QuickSight',
        'Get access to Superset',
        'Get access to Data Explorer'
      ].forEach((name) => {
        cy.findByRole('link', { name }).should(
          'have.attr',
          'href',
          '/request-access/self-certify'
        );
      });
    });
    it('should be directed to the self certify form', () => {
      cy.visit('/tools');
      cy.findByRole('link', { name: 'Get access to QuickSight' }).click();
      cy.findByRole('heading', { name: 'Get access to tools', level: 1 });
      cy.findByText(
        /To get access to tools you need to have completed the/
      ).should('be.visible');
      cy.findByRole('link', { name: 'Security and Data Protection' }).should(
        'have.attr',
        'href',
        'https://www.learninghub.businessandtrade.gov.uk/c/portal/learning-path/open?plid=2224131&lpId=434'
      );
      cy.findByText(
        /training. It's mandatory for all DBT staff and needs to be completed every 12 months./
      ).should('be.visible');
      cy.findByText(
        /Once you have verified your training is up to date, you will get access to:/
      ).should('be.visible');
      [
        'Quicksight',
        'pgAdmin',
        'Data Explorer',
        'RStudio',
        'JupyterLab Python',
        'Theia',
        'Your Files'
      ].forEach((text) => cy.findByText(text));
      cy.findByRole('heading', {
        name: 'How to verify your training is up to date',
        level: 2
      });
      cy.findByText(
        'You need to give us the date that\'s on your Security and Data Protection certificate by entering it into the boxes below.'
      ).should('be.visible');
      cy.findByRole('group', {
        name: 'Enter the date that\'s on your certificate'
      });
      cy.findByText('For example, 27 3 2007');
      cy.findByRole('textbox', {
        name: 'Day'
      });
      cy.findByRole('textbox', {
        name: 'Month'
      });
      cy.findByRole('textbox', {
        name: 'Year'
      });
      cy.findByRole('textbox', {
        name: 'Year'
      });
      cy.findByRole('heading', { name: 'Declaration', level: 2 });
      cy.findByRole('checkbox', {
        name: 'I confirm that I\'ve completed the Security and Data Protection training and the date I\'ve entered matches my certificate.'
      });
      cy.findByRole('button', { name: 'Submit' });
      cy.findByRole('link', { name: 'Cancel' });
    });
  });

  context('When a user submits an invalid form.', () => {
    beforeEach(() => {
      cy.visit('/request-access/self-certify');
    });

    it('should error when date is empty', () => {
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'Enter the date that\'s on your Security and Data Protection certificate'
      ]);
    });

    it('should error when day is empty', () => {
      setCertificateDate(' ', '01', '2024');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });

    it('should error when month is empty', () => {
      setCertificateDate('01', ' ', '2024');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });

    it('should error when year is empty', () => {
      setCertificateDate('01', '01', ' ');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });

    it('should error when date is NOT numeric', () => {
      setCertificateDate('test', 'test', 'test');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });

    it('should error when the declaration has NOT been checked', () => {
      setCertificateDate('01', '01', '2024');
      cy.findByRole('button', { name: 'Submit' }).click();
      cy.findByRole('link', {
        name: 'Check the box to agree with the declaration statement'
      });
    });

    it('should error when date is empty and the declaration has NOT been checked', () => {
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'Enter the date that\'s on your Security and Data Protection certificate'
      ]);
      cy.findByRole('link', {
        name: 'Check the box to agree with the declaration statement'
      });
    });

    it('should error when the declaration has NOT been checked and date is older than a year from today', () => {
      setCertificateDate('01', '01', '2023');
      cy.findByRole('button', { name: 'Submit' }).click();
      cy.findByRole('link', {
        name: 'Check the box to agree with the declaration statement'
      });
      assertErrorMessages([
        'Enter the date that’s on your security and data protection certificate, this date must be today or within the past 12 months'
      ]);
    });

    it('should error when the declaration has NOT been checked and date is in the future', () => {
      setCertificateDate('01', '01', '2025');
      cy.findByRole('button', { name: 'Submit' }).click();
      cy.findByRole('link', {
        name: 'Check the box to agree with the declaration statement'
      });
      assertErrorMessages([
        'Enter the date that’s on your security and data protection certificate, this date must be today or within the past 12 months'
      ]);
    });

    it('should error when the declaration has NOT been checked and date is NOT valid', () => {
      setCertificateDate('30', '02', '2024');
      cy.findByRole('button', { name: 'Submit' }).click();
      cy.findByRole('link', {
        name: 'Check the box to agree with the declaration statement'
      });
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });

    it('should error when certifcate date is older than a year from today', () => {
      setCertificateDate('01', '01', '2023');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'Enter the date that’s on your security and data protection certificate, this date must be today or within the past 12 months'
      ]);
    });

    it('should error when certifcate date is in the future', () => {
      setCertificateDate('01', '01', '2025');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'Enter the date that’s on your security and data protection certificate, this date must be today or within the past 12 months'
      ]);
    });

    it('should error when certifcate date is NOT a valid date', () => {
      setCertificateDate('31', '02', '2024');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      assertErrorMessages([
        'The date on your Security and Data Protection certificate must be a real date'
      ]);
    });
  });

  context('When a user successfully submits the form', () => {
    it('should show a success message and have access to tools', () => {
      cy.visit('/request-access/self-certify');
      setCertificateDate('01', '02', '2024');
      acceptDeclaration();
      cy.findByRole('button', { name: 'Submit' }).click();
      cy.findByRole('alert').within(() => {
        cy.findByRole('heading', {
          name: 'You\'ve been granted tools access',
          level: 3
        }).should('be.visible');
        cy.findByText(/Find out how to/).should('be.visible');
        cy.findByRole('link', { name: 'get started with tools' }).should(
          'have.attr',
          'href',
          'https://data-services-help.trade.gov.uk/data-workspace/how-to/use-tools/'
        );
      });
    });
    it('should be able to access all the tools', () => {
      cy.visit('/tools/');
      cy.findByRole('link', { name: 'Open QuickSight' }).should(
        'have.attr',
        'href',
        '/tools/quicksight/redirect'
      );
      cy.findByRole('link', { name: 'Open Superset' }).should(
        'have.attr',
        'href',
        '/tools/superset/redirect'
      );
      cy.findByRole('link', { name: 'Open Data Explorer' }).should(
        'have.attr',
        'href',
        '/tools/explorer/redirect'
      );
    });
  });
});
