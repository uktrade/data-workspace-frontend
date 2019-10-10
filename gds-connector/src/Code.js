///////////////////////
// Fetching data
///////////////////////

function getConfig() {
  return {
    dateRangeRequired: false,
  };
}

function dataWorkspaceRequest(path) {
  var scriptProperties = PropertiesService.getScriptProperties();
  var response = UrlFetchApp.fetch(scriptProperties.getProperty('DATA_WORKSPACE_URL') + path, {
    headers: {
      Authorization: 'Bearer ' + getDataWorkspaceOAuth2Service().getAccessToken(),
    },
  })
  var response_text = response.getContentText();
  return JSON.parse(response_text);
}

function getSchema() {
  return dataWorkspaceRequest('api/v1/table/some-id/schema');
}

function getData(request) {
  return dataWorkspaceRequest('api/v1/table/some-id/rows');
}


///////////////////////
// Authentication
///////////////////////

function getAuthType() {
  return {
    type: "OAUTH2",
  };
}

function getDataWorkspaceOAuth2Service() {
  var scriptProperties = PropertiesService.getScriptProperties();
  return OAuth2.createService('data-workspace')
      .setAuthorizationBaseUrl(scriptProperties.getProperty('SSO_URL') + 'o/authorize/')
      .setTokenUrl(scriptProperties.getProperty('SSO_URL') + 'o/token/')
      .setClientId(scriptProperties.getProperty('SSO_CLIENT_ID'))
      .setClientSecret(scriptProperties.getProperty('SSO_CLIENT_SECRET'))
      .setGrantType('authorization_code')
      .setCallbackFunction('authCallback')
      .setPropertyStore(PropertiesService.getUserProperties())  // Where the token is stored
      .setScope('read write');
}

function authCallback(request) {
  var dataWorkspaceOauth2Service = getDataWorkspaceOAuth2Service();
  var isAuthorized = dataWorkspaceOauth2Service.handleCallback(request);
  if (isAuthorized) {
    return HtmlService.createHtmlOutput('Authorization complete. You should close this window.');
  } else {
    return HtmlService.createHtmlOutput('Denied. You should close this window');
  }
}

function resetAuth() {
  getDataWorkspaceOAuth2Service().reset();
}

function isAuthValid() {
  return getDataWorkspaceOAuth2Service().hasAccess();
}

function get3PAuthorizationUrls() {
  return getDataWorkspaceOAuth2Service().getAuthorizationUrl();
}

function logout() {
  getDataWorkspaceOAuth2Service().reset();
}
