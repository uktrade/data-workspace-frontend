var POLL_DELAY = 1000;
var FAILURE_STATES = ['failed', 'upstream_failed'];

function buildFailureUrl(failureRedirectUrl, taskName) {
  var queryParams = Object.fromEntries(new URLSearchParams(location.search))
  queryParams.task_name = taskName;
  return failureRedirectUrl + '?' + Object.keys(queryParams).map(function(key) {
      return key + '=' + queryParams[key]
  }).join('&');
}

function pollForDagStateChange(taskStatusUrl, successRedirectUrl, failureRedirectUrl, taskName) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', taskStatusUrl);
  xhr.onreadystatechange = function() {

    if (this.readyState === XMLHttpRequest.DONE) {
      if (this.status === 200) {
        var resp = JSON.parse(xhr.responseText);
        if (resp.state === 'success') {
          window.location.href = successRedirectUrl;
        }
        if (FAILURE_STATES.includes(resp.state)) {
          window.location.href = buildFailureUrl(failureRedirectUrl, taskName);
        }
        setTimeout(function () {
          pollForDagStateChange(
              taskStatusUrl,
              successRedirectUrl,
              failureRedirectUrl,
              taskName
          )
        }, POLL_DELAY);
      }
      else {
        window.location.href = buildFailureUrl(failureRedirectUrl, taskName);
      }
    }
  }
  xhr.send()
}
window.pollForDagStateChange = pollForDagStateChange;
