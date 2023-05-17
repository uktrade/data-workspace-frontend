document.getElementById("shareDashboardPopUp").addEventListener("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    const copyButton = document.getElementById("copy-to-clipboard");
    copyButton.innerText = "Copy link to dashboard";
    copyButton.classList.remove("govuk-button--disabled");
    copyButton.disabled = false;
    document.getElementById("popup").showModal();
  }
);

document.getElementById("closePopUp").addEventListener("click", function () {
   document.getElementById("popup").close();
    
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
        })
        .catch((error) => {
        });
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = textAreaInput;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      copyButton.innerText = "Link copied";
      copyButton.classList.add("govuk-button--disabled")
      copyButton.disabled = true;
    }
  }
);
