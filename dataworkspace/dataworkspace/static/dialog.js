document.addEventListener("DOMContentLoaded", function () {
  const links = document.querySelectorAll("a[data-modal-id]");

  links.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const modalId = e.target.getAttribute("data-modal-id");
      const modal = document.getElementById(`modal${modalId}`);

      modal.showModal();

      button = modal.querySelector("button[data-modal-id]");
      button.addEventListener("click", function () {
        modal.close();
      });
    });
  });
});
