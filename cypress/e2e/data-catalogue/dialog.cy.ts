import {
  datacutWithLinks,
  datacutWithTableAndLinks
} from '../../fixtures/datasets';
import { sourceLink1, sourceLink2 } from '../../fixtures/source-link-ids';

type sourceID = typeof sourceLink1 | typeof sourceLink2 | 1;
type filename = 'download.csv' | 'download-2.csv';
type headerFilename = 'source_link_1.csv' | 'source_link_2.csv';
type linkTitle = 'Source link 1' | 'Source link 2';

describe('Dialog notification', () => {
  function visitSourceLinkPageAndDownload(
    filename: filename = 'download.csv',
    headerFilename: headerFilename = 'source_link_1.csv',
    linkTitle: linkTitle = 'Source link 1',
    sourceID: sourceID = sourceLink1
  ) {
    cy.intercept('GET', `**/${filename}`, {
      statusCode: 200,
      body: '',
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename=${headerFilename}`
      }
    }).as('getSourceLinkDownload');

    cy.visit(`/datasets/${datacutWithLinks}`);
    cy.findByRole('link', { name: linkTitle }).click();
    cy.findByRole('link', { name: 'Download data as CSV' })
      .should(
        'have.attr',
        'href',
        `/datasets/${datacutWithLinks}/link/${sourceID}/download`
      )
      .click();
    cy.wait('@getSourceLinkDownload');
  }

  function visitSourceTablePageAndDownload() {
    cy.intercept('POST', '**/data?download=1', {
      statusCode: 200,
      body: '',
      headers: {
        'Content-Type': 'text/csv'
      }
    }).as('getSourceTableDownload');

    cy.visit(`/datasets/${datacutWithTableAndLinks}`);
    cy.findByRole('link', { name: 'Some report' }).click();
    cy.findByRole('button', { name: 'Download this data' }).click();
    cy.findByRole('dialog').within(() => {
      cy.findByRole('button', { name: 'Download this data' }).click();
      cy.wait('@getSourceTableDownload');
    });
  }

  function assertFeedbackBannerExists(sourceID: sourceID) {
    cy.findByRole('dialog')
      .should('be.visible')
      .within(() => {
        cy.findByText('Important').should('be.visible');
        cy.findByText('A copy of this data should now be downloading.').should(
          'be.visible'
        );
      });
    cy.findByRole('link', { name: 'feedback form.' }).should(
      'have.attr',
      'href',
      `/feedback?survey_source=csat-link&id=${sourceID}`
    );
  }

  function assertFeedbackBannerDoesNotExists() {
    cy.findByRole('dialog')
      .should('be.visible')
      .within(() => {
        cy.findByText('Important').should('not.be.visible');
        cy.findByText('A copy of this data should now be downloading.').should(
          'not.be.visible'
        );
      });
    cy.findAllByRole('link', { name: 'feedback form.' }).should('not.exist');
  }

  context(
    'When downloading table data from a data cut page for the first time',
    () => {
      it('should show a dialog with a feedback banner notification', () => {
        cy.getCookie('notificationLastShown').should('not.exist');
        visitSourceTablePageAndDownload();
        assertFeedbackBannerExists(1);
        cy.getCookie('notificationLastShown').should('exist');
      });
    }
  );

  context(
    'When downloading table data from a data cut page for the second time',
    () => {
      it('should NOT show a dialog with feedback banner notification', () => {
        cy.getCookie('notificationLastShown').should('not.exist');
        visitSourceTablePageAndDownload();
        cy.getCookie('notificationLastShown').should('exist');
        visitSourceTablePageAndDownload();
        assertFeedbackBannerDoesNotExists();
      });
    }
  );

  context(
    'When downloading a source link from a data cut page for the first time',
    () => {
      it('should show a dialog with a feedback banner notification', () => {
        cy.getCookie('notificationLastShown').should('not.exist');
        visitSourceLinkPageAndDownload();
        assertFeedbackBannerExists(sourceLink1);
      });
    }
  );

  context(
    'When downloading a source link from a data cut page for the second time',
    () => {
      it('should NOT show a dialog with feedback banner notification', () => {
        cy.getCookie('notificationLastShown').should('not.exist');
        visitSourceLinkPageAndDownload();
        assertFeedbackBannerExists(sourceLink1);
        cy.getCookie('notificationLastShown').should('exist');
        visitSourceLinkPageAndDownload();
        assertFeedbackBannerDoesNotExists();
      });
    }
  );

  context('When downloading from two source links', () => {
    it('should show unique source links', () => {
      cy.getCookie('notificationLastShown').should('not.exist');
      visitSourceLinkPageAndDownload();
      assertFeedbackBannerExists(sourceLink1);
      cy.getCookie('notificationLastShown').should('exist');
      visitSourceLinkPageAndDownload(
        'download-2.csv',
        'source_link_2.csv',
        'Source link 2',
        sourceLink2
      );
      assertFeedbackBannerDoesNotExists();
    });
  });

  context('When the user clicks the feedback link', () => {
    it('should redirect to the feedback form with analyse data pre-selected', () => {
      visitSourceLinkPageAndDownload();

      cy.findByRole('link', { name: 'feedback form.' }).click();
      cy.url().should('include', '/feedback/?survey_source=csat-link');

      cy.findByLabelText('Analyse data').should('be.checked');
    });

    it('should show dialog and banner when user clicks back to source link', () => {
      visitSourceLinkPageAndDownload();

      cy.findByRole('link', { name: 'feedback form.' }).click();
      cy.findByRole('link', { name: 'Back' }).click();

      cy.findByRole('dialog')
        .within(() => {
          cy.findByText('Important').should('be.visible');
        })
        .should('be.visible');
    });

    it('should show dialog and banner when user clicks back to source table', () => {
      visitSourceTablePageAndDownload();

      cy.findByRole('link', { name: 'feedback form.' }).click();
      cy.findByRole('link', { name: 'Back' }).click();

      cy.findByRole('dialog')
        .within(() => {
          cy.findByText('Important').should('be.visible');
        })
        .should('be.visible');
    });
  });
});
