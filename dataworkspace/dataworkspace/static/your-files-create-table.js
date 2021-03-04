var POLL_DELAY = 1000;
var FAILURE_STATES = ['failed', 'upstream_failed'];

function pollForDagStateChange(taskStatusUrl, successRedirectUrl, failureRedirectUrl) {
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
          window.location.href = failureRedirectUrl;
        }
        setTimeout(function () {
          pollForDagStateChange(
              taskStatusUrl,
              successRedirectUrl,
              failureRedirectUrl
          )
        }, POLL_DELAY);
      }
      else {
        window.location.href = failureRedirectUrl;
      }
    }
  }
  xhr.send()
}
window.pollForDagStateChange = pollForDagStateChange;
