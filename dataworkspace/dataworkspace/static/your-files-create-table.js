var DELAY_STEP = 250;
var MAX_DELAY = 5000;

function pollForDagStateChange(executionDate, successStates, successRedirectUrl, failureRedirectUrl, pollDelay) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/files/create-table/status/' + executionDate);
  xhr.onreadystatechange = function() {
    if (this.readyState === XMLHttpRequest.DONE) {
      if (this.status === 200) {
        var resp = JSON.parse(xhr.responseText);
        if (successStates.includes(resp.state)) {
          window.location.href = successRedirectUrl;
        }
        else if (resp.state === "failed") {
          window.location.href = failureRedirectUrl;
        }
        else {
          setTimeout(function () {
            pollForDagStateChange(
                executionDate,
                successStates,
                successRedirectUrl,
                failureRedirectUrl,
                Math.min(pollDelay + DELAY_STEP, MAX_DELAY),
            )
          }, pollDelay);
        }
      }
      else {
        window.location.href = failureRedirectUrl;
      }
    }
  }
  xhr.send()
}
window.pollForDagStateChange = pollForDagStateChange;
