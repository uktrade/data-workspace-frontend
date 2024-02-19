const setCookie = (name, value, expiry) => {
  let expires = "";
  if (expiry) {
    const date = new Date();
    date.setTime(date.getTime() + expiry);
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = `${name}=${value}${expires}; path=/`;
};

const getCookie = (name) => {
  const regex = new RegExp(`(^| )${name}=([^;]+)`);
  const match = document.cookie.match(regex);
  if (match) {
    return match[2];
  }
};

const showFeedbackBanner = (id, visible = false) => {
  document.querySelector(
    `[data-feedback-notification-id="${id}"]`
  ).style.display = visible ? "block" : "none";
};

const showNotification = (e) => {
  const id = e.target.getAttribute("data-download-id");
  const lastShown = getCookie("notificationLastShown");
  const oneWeek = 7 * 24 * 60 * 60 * 1000;
  const currentTime = new Date().getTime();

  if (!lastShown || currentTime - lastShown > oneWeek) {
    showFeedbackBanner(id, true);
    setCookie("notificationLastShown", currentTime, oneWeek);
  }
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".download-data").forEach((link) => {
    link.addEventListener("click", showNotification);
  });

  const modals = document.querySelectorAll("dialog");
  const modalLinks = document.querySelectorAll("a[data-modal-ref-id]").length
    ? document.querySelectorAll("a[data-modal-ref-id]")
    : document.querySelectorAll("button[data-modal-ref-id]");
  if (modals) {
    modalLinks.forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const id = e.target.getAttribute("data-modal-ref-id");
        const modal = document.querySelector(`dialog[data-modal-id="${id}"]`);
        showFeedbackBanner(id, false);
        modal.showModal();
      });
    });

    modals.forEach((modal) => {
      const closeButton = modal.querySelector("button:last-child");
      if (closeButton) {
        closeButton.addEventListener("click", () => modal.close());
      }
    });
  }
});

if (document.referrer.includes("feedback")) {
  const url = new URL(document.referrer);
  const params = new URLSearchParams(url.search);
  const id = params.get("id");

  showFeedbackBanner(id, true);
  document.querySelector("dialog").showModal();
}
