import * as dayjs from 'dayjs';

const oneMonthFromNow = dayjs().add(1, 'month').format('YYYY-MM-DD');
const oneDaysTime = dayjs().add(1, 'day').format('YYYY-MM-DD');
const twoDaysFromNow = dayjs().add(2, 'day').format('YYYY-MM-DD');
const threeDaysFromNow = dayjs().add(3, 'day').format('YYYY-MM-DD');
const yesterday = dayjs().subtract(1, 'day').format('YYYY-MM-DD');

const setUpAliases = () => {
  cy.findByRole('region', {
    name: 'This is a notification. To engage with this information follow this link.'
  })
    .as('notification')
    .within(() => {
      cy.findByRole('link', { name: 'follow this link' })
        .should('have.attr', 'href', '/datasets')
        .as('link');
      cy.findByRole('link', { name: 'Dismiss' }).as('dismissLink');
    });
};

const assertLastChanceContentIsVisible = () => {
  cy.findByRole('region', {
    name: 'This is the last chance content as this notification expires in x days time.'
  }).should('be.visible');
};

const assertNotificationBannerDoesNotExist = () => {
  cy.findAllByRole('region', {
    name: 'This is a notification. To engage with this information follow this link.'
  }).should('not.exist');
};

describe('Notification banner', () => {
  context('When a user visits the homepage with an active notification', () => {
    beforeEach(() => {
      cy.updateNotificationBanner(1, 7, oneMonthFromNow);
      setUpAliases();
    });

    it('should display a notification banner', () => {
      cy.get('@notification').should('be.visible');
      cy.get('@link').should('be.visible');
      cy.get('@dismissLink').should('be.visible');
    });
  });
  context(
    'When a user engages with the banner on the homepage by clicking a link',
    () => {
      beforeEach(() => {
        cy.updateNotificationBanner(1, 7, oneMonthFromNow);
        setUpAliases();
      });
      it('should hide the notification banner', () => {
        cy.intercept('GET', '/datasets').as('datasets');
        cy.intercept('GET', '*').as('home');
        cy.get('@link').click();
        cy.wait('@datasets');
        cy.visit('/');
        cy.wait('@home');
        assertNotificationBannerDoesNotExist();
      });
    }
  );
  context('When a user dismisses the notification banner', () => {
    beforeEach(() => {
      cy.updateNotificationBanner(1, 7, oneMonthFromNow);
      setUpAliases();
    });
    it('should hide the notification banner', () => {
      cy.get('@dismissLink').click();
      assertNotificationBannerDoesNotExist();
    });
    it('should show the last chance notification banner when the notification expiry date is within 3 days time', () => {
      cy.get('@dismissLink').click();
      cy.updateNotificationBanner(1, 3, threeDaysFromNow);
      assertLastChanceContentIsVisible();
    });
    it('should show the last chance notification banner when the notification expiry date is within 2 days time', () => {
      cy.get('@dismissLink').click();
      cy.updateNotificationBanner(1, 2, twoDaysFromNow);
      assertLastChanceContentIsVisible();
    });
    it('should show the last chance notification banner when the notification expiry date is within 1 days time', () => {
      cy.get('@dismissLink').click();
      cy.updateNotificationBanner(1, 1, oneDaysTime);
      assertLastChanceContentIsVisible();
    });
    it('should NOT show the notification banner when the notification has expired', () => {
      cy.updateNotificationBanner(1, 0, yesterday);
      assertNotificationBannerDoesNotExist();
    });
  });
});
