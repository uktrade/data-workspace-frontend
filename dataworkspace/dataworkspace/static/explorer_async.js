function pollForQueryResults(queryLogId, delay, delayStep, maxDelay) {
  var resultsContainer = document.getElementById('query-results');
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/data-explorer/logs/' + queryLogId + '/results-json/');
  xhr.onreadystatechange = function() {
    if (this.readyState === XMLHttpRequest.DONE) {
      var resp = JSON.parse(xhr.responseText);
      resultsContainer.innerHTML = resp.html;
      if (resp.state === 0) {
        setTimeout(function () {
          pollForQueryResults(queryLogId, Math.min(delay + delayStep, maxDelay), delayStep, maxDelay)
        }, delay)
      }
      else if (resp.state === 1) {
        document.getElementById('error-summary').innerHTML = resp.error;
        document.getElementById('error-banner').classList.remove('govuk-!-display-none');
        document.getElementById('id_sql').classList.add('govuk-form-group--error');
        document.getElementById('inline-error').innerHTML = '<span id="sql-error" class="govuk-error-message">' + resp.error + '</span>'
        document.getElementById('inline-error').classList.remove('govuk-!-display-none');
      }
    }
  }
  xhr.send()
}
window.pollForQueryResults = pollForQueryResults;
