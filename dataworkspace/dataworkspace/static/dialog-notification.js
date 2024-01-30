function setCookie(name, value, days) {
  let expires = "";
  if (days) {
    const date = new Date();
    date.setTime(date.getTime() + (days*24*60*60*1000));
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = `${name}=${value}${expires}; path=/`;
}

function getCookie(name) {
  {
    const regex = new RegExp(`(^| )${name}=([^;]+)`)
    const match = document.cookie.match(regex)
    if (match) {
      return match[2]
    }
  }
}

function addButtonListener(elementId) {
  var element = document.getElementById(elementId);
  if (element) {
    element.addEventListener("click", showNotification);
  }
}

function showNotification() {
  var lastShown = getCookie("notificationLastShown");
  var oneWeek = 7 * 24 * 60 * 60 * 1000;
  var currentTime = new Date().getTime();

  if (!lastShown || (currentTime - lastShown > oneWeek)) {
    document.getElementById('feedbackNotification').style.display = 'block';
    setCookie("notificationLastShown", currentTime, 7);
  }
}

addButtonListener("data-grid-download");
addButtonListener("data-grid-json-download");