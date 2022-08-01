var QUERY_STATE_RUNNING = 0;
var QUERY_STATE_FAILED = 1;
var QUERY_STATE_CANCELLED = 3;

function pollForQueryResults(queryLogId, delay, delayStep, maxDelay) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/data-explorer/logs/' + queryLogId + '/results-json/');
  xhr.onreadystatechange = function() {
    if (this.readyState === XMLHttpRequest.DONE) {
      var resp = JSON.parse(xhr.responseText);
      if (resp.state === QUERY_STATE_RUNNING) {
        setTimeout(function () {
          pollForQueryResults(queryLogId, Math.min(delay + delayStep, maxDelay), delayStep, maxDelay)
        }, delay)
      }
      else if (resp.state === QUERY_STATE_FAILED || resp.state === QUERY_STATE_CANCELLED) {
        document.getElementById('error-summary').innerHTML = resp.error;
        document.getElementById('error-banner').classList.remove('govuk-!-display-none');
        document.getElementById('id_sql').classList.add('govuk-form-group--error');
        document.getElementById('inline-error').innerHTML = '<span id="sql-error" class="govuk-error-message">' + resp.error + '</span>'
        document.getElementById('inline-error').classList.remove('govuk-!-display-none');
        document.getElementById('async-query-executing').classList.add('govuk-!-display-none');
        document.getElementById('async-query-submitting').classList.add('govuk-!-display-none');
      }
      else {
        document.getElementById('query-results-wrapper').innerHTML = resp.html;
      }
    }
  }
  xhr.send()
}
window.pollForQueryResults = pollForQueryResults;


function cancel_query(event) {
  document.getElementById(event.target.id).disabled = true;
  var csrf = document.getElementsByName("csrfmiddlewaretoken")[0].value;
  var xhr = new XMLHttpRequest();
  xhr.open('POST', 'cancel/', true);
  xhr.setRequestHeader("X-CSRFToken", csrf);
  xhr.setRequestHeader("Content-Type", "text/plain;charset=UTF-8");
  xhr.send();
}
var el = document.getElementById('cancel_query');
if(el){
  el.addEventListener('click', cancel_query, false);
}
