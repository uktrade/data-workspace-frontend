document.addEventListener("DOMContentLoaded", () =>
  document.querySelectorAll(".modal-link").forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const modal = e.target.nextElementSibling;
      modal.showModal();
      const closeButton =
        modal.getElementsByTagName("button")[
          modal.getElementsByTagName("button").length - 1
        ];
      closeButton.addEventListener("click", () => modal.close());
    })
  )
);
