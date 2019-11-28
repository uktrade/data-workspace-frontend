///////////////////////
// Errors appear in logs if this function not present
///////////////////////

function isAdminUser() {
  return false;
}


///////////////////////
// Fetching data
///////////////////////

function getConfig() {
  console.info('getConfig');
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

function dataWorkspaceRequest(path, data) {
  console.info('dataWorkspaceRequest', path, data);
  try {
    var scriptProperties = PropertiesService.getScriptProperties();
    var response = UrlFetchApp.fetch(scriptProperties.getProperty('DATA_WORKSPACE_URL') + path, {
      method: 'post',
      contentType: 'application/json',
      headers: {
        Authorization: 'Bearer ' + getDataWorkspaceOAuth2Service().getAccessToken(),
      },
      payload: JSON.stringify(data),
    });
    console.info('dataWorkspaceRequest: response.getResponseCode()', response.getResponseCode());
    console.info('dataWorkspaceRequest: response.getHeaders()', response.getHeaders());
    var response_text = response.getContentText();
    console.info('dataWorkspaceRequest: response.getContentText().length', response_text.length);
    return JSON.parse(response_text);
  } catch (e) {
    console.error('dataWorkspaceRequest: exception', e);
    DataStudioApp.createCommunityConnector()
      .newUserError()
      .setText('Error fetching from ' + data + '. Exception details: ' + e)
      .throwException();    
  }
}

function validateRequest(request) {
   console.info('validateRequest', request);
   if (!request.configParams || !request.configParams.tableId) {
      console.error('validateRequest: invalid', request);
      DataStudioApp.createCommunityConnector()
        .newUserError()
        .setText('Please enter the Table ID')
        .throwException();
  }
}

function getSchema(request) {
  console.info('getSchema', request);
  validateRequest(request);
  return dataWorkspaceRequest('api/v1/table/' + request.configParams.tableId + '/schema', request);
}

function getData(request) {
  console.info('getData', request);
  validateRequest(request);
  var url = 'api/v1/table/' + request.configParams.tableId + '/rows'
  
  var data = dataWorkspaceRequest(url, request)
  var searchAfter = data.$searchAfter;

  while (searchAfter) {
    request.$searchAfter = searchAfter;
    data_page = dataWorkspaceRequest(url, request);
    data.rows = data.rows.concat(data_page.rows);
    searchAfter = data_page.$searchAfter;
  }
  
  return data;
}


///////////////////////
// Authentication
///////////////////////

function getAuthType() {
  console.info('getAuthType');
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
  console.info('authCallback', request);
  try {
    var dataWorkspaceOauth2Service = getDataWorkspaceOAuth2Service();
    var isAuthorized = dataWorkspaceOauth2Service.handleCallback(request);
    console.info('authCallback: isAuthorized', isAuthorized);
    if (isAuthorized) {
      return HtmlService.createHtmlOutput('Authorization complete. You should close this window.');
    } else {
      return HtmlService.createHtmlOutput('Denied. You should close this window');
    }
  } catch (e) {
    console.error('authCallback: exception', e);
    throw (e);
  }
}

function resetAuth() {
  console.info('resetAuth');
  try {
    getDataWorkspaceOAuth2Service().reset();
  } catch (e) {
    console.error('resetAuth: exception', e);
    throw (e);
  }
  console.info('resetAuth: end');
}

function isAuthValid() {
  try {
    return getDataWorkspaceOAuth2Service().hasAccess();
  } catch (e) {
    console.error('isAuthValid: exception', e);
    throw (e);
  }
}

function get3PAuthorizationUrls() {
  console.info('get3PAuthorizationUrls');
  try {
    return getDataWorkspaceOAuth2Service().getAuthorizationUrl();
  } catch (e) {
    console.error('get3PAuthorizationUrls: exception', e);
    throw (e);
  }
}

function logout() {
  console.info('logout');
  try {
    getDataWorkspaceOAuth2Service().reset();
  } catch (e) {
    console.error('logout: exception', e);
    throw (e);
  }
  console.info('logout: end');
}
