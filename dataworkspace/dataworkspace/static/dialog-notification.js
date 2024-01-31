function setCookie(name, value, expiry) {
  let expires = "";
  if (expiry) {
    const date = new Date();
    date.setTime(date.getTime() + expiry);
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = `${name}=${value}${expires}; path=/`;
}

function getCookie(name) {
  {
    const regex = new RegExp(`(^| )${name}=([^;]+)`);
    const match = document.cookie.match(regex);
    if (match) {
      return match[2];
    }
  }
}

function addButtonListener(elementId, functionCall = showNotification) {
  var element = document.getElementById(elementId);
  if (element) {
    element.addEventListener("click", functionCall);
  }
}

function showFeedbackBanner() {
  document.getElementById("feedback-notification").style.display = "block";
}

function showNotification() {
  var lastShown = getCookie("notificationLastShown");
  var oneWeek = 7 * 24 * 60 * 60 * 1000;
  var currentTime = new Date().getTime();

  if (!lastShown || currentTime - lastShown > oneWeek) {
    showFeedbackBanner();
    setCookie("notificationLastShown", currentTime, oneWeek);
  }
}

function feedbackLinkCookie() {
  var oneMinute = 60 * 1000;
  var currentTime = new Date().getTime();

  setCookie("feedbackLinkClicked", currentTime, oneMinute);
}

addButtonListener("data-grid-download");
addButtonListener("data-grid-json-download");
addButtonListener("feedback-link", feedbackLinkCookie);

if (getCookie("feedbackLinkClicked") && document.referrer.includes("feedback")) {
  showFeedbackBanner();
  document.getElementById("download-dialog").showModal();
}