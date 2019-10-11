///////////////////////
// Fetching data
///////////////////////

function getConfig() {
  return {
    configParams: [{
      type: 'TEXTINPUT',
      name: 'tableId',
      displayName: 'Table ID',
      placeholder: 'the-table-id',
      helpText: 'The ID of the Data Workspace table',
    }],
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

function validateRequest(request) {
   if (!request.configParams || !request.configParams.tableId) {
      DataStudioApp.createCommunityConnector()
        .newUserError()
        .setText('Please enter the Table ID')
        .throwException();
  }
}

function getSchema(request) {
  validateRequest(request);
  return dataWorkspaceRequest('api/v1/table/' + request.configParams.tableId + '/schema');
}

function getData(request) {
  validateRequest(request);
  return dataWorkspaceRequest('api/v1/table/' + request.configParams.tableId + '/rows');
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
