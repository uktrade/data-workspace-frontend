document.getElementById("shareDashboardPopUp").addEventListener("click", function () {
    document.getElementById("popup").style.display = "block";
    document.getElementById("popup-background").style.display = "block";
  }
);

document.getElementById("closePopUp").addEventListener("click", function () {
    document.getElementById("popup").style.display = "none";
    document.getElementById("popup-background").style.display = "none";
  }
);

document.getElementById("copy-to-clipboard").addEventListener("click", function () {
    const textAreaInput = document.getElementById("share-dashboard").value;
    const copyButton = document.getElementById("copy-to-clipboard")

    if (navigator.clipboard) {

      navigator.clipboard.writeText(textAreaInput)
        .then(() => {
          copyButton.innerText = "Link copied";
          copyButton.classList.add("govuk-button--disabled")
          copyButton.disabled = true;
          console.log("Text copied to clipboard with navigator")
        })
        .catch((error) => {
          console.error("Error copying text to clipboard:", error);
        });
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = textAreaInput;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      console.log("Text copied to clipboard");
      copyButton.innerText = "Link copied";
      copyButton.classList.add("govuk-button--disabled")
      copyButton.disabled = true;
    }
  }
);
