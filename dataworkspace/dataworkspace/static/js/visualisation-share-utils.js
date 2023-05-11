function showShareDashboardPopUp() {
  document.getElementById("popup").style.display = "block";
  document.getElementById("popup-background").style.display = "block";
  document.getElementById("share-dashboard").value = window.location.href;
}

function hidePopup() {
  document.getElementById("popup").style.display = "none";
  document.getElementById("popup-background").style.display = "none";
}

function copyToClipboard() {
  const textAreaInput = document.getElementById("share-dashboard").innerText;

  navigator.clipboard.writeText(textAreaInput)
    .then(() => {
      this.value = "Link copied";
      this.classList.add("govuk-button--disabled")
      this.disabled = true;
    })
    .catch((error) => {
      console.error("Error copying text to clipboard:", error);
    });
}
