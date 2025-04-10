import '@testing-library/cypress/add-commands';
import './setup-cypress-testing-library';
/// <reference types="cypress" />

const resetUserPermissions = (dataSetId) => {
  // First go to home page to pick up CSRF cookie
  cy.visit('/');
  cy.getCookie('data_workspace_csrf').then((c) =>
    cy.request({
      url: `/test/dataset/${dataSetId}/delete-user-permissions`,
      method: 'DELETE',
      headers: {
        'X-CSRFToken': c.value
      }
    })
  );
};

const setUsersEditorAccess = (dataSetId, hasEditorAccess) => {
  // First go to home page to pick up CSRF cookie
  cy.visit('/');
  cy.getCookie('data_workspace_csrf').then((c) =>
    cy.request({
      url: `/test/dataset/${dataSetId}`,
      method: 'PATCH',
      headers: {
        'X-CSRFToken': c.value
      },
      body: {
        data_catalogue_editors: [hasEditorAccess ? 2 : 1]
      }
    })
  );
};

const updateNotificationBanner = (notificationId, lastChanceDays, endDate) => {
  // First go to home page to pick up CSRF cookie
  cy.visit('/');
  cy.getCookie('data_workspace_csrf').then((c) =>
    cy.request({
      url: `/test/notification/${notificationId}`,
      method: 'PATCH',
      headers: {
        'X-CSRFToken': c.value
      },
      body: {
        last_chance_days: lastChanceDays,
        end_date: endDate
      }
    })
  );
  cy.reload();
};

// Sets wether or not the user has editor access on a dataset
Cypress.Commands.add('setUsersEditorAccess', (dataSetId, hasEditorAccess) =>
  setUsersEditorAccess(dataSetId, hasEditorAccess)
);

// Resets the user permissions on a dataset
Cypress.Commands.add('resetUserPermissions', (dataSetId) =>
  resetUserPermissions(dataSetId)
);

// Resets all permissions on a dataset
Cypress.Commands.add('resetAllPermissions', (dataSetId) => {
  setUsersEditorAccess(dataSetId, false);
  resetUserPermissions(dataSetId);
});

// Updates the expiry date and last chance days on the notification banner
Cypress.Commands.add(
  'updateNotificationBanner',
  (notificationId, lastChanceDays, endDate) =>
    updateNotificationBanner(notificationId, lastChanceDays, endDate)
);

/**
 * Custom Cypress command to get the open confirmation dialog.
 *
 * This command retrieves the element with the `data-test="confirmation-dialog"` attribute,
 * asserts that it is visible, and then asserts that it has the `open` attribute.
 * It yields the jQuery element representing the open confirmation dialog.
 *
 * @example
 * cy.getOpenDialog().within(() => {
 *   cy.contains('Confirm').click();
 * });
 */
Cypress.Commands.add('getOpenDialog', () => {
  return cy
    .get('[data-test="confirmation-dialog"]')
    .should('be.visible')
    .then(($el) => {
      expect($el).to.have.attr('open');
      return $el;
    });
});
