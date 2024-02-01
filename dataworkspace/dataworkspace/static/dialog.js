window.onload = function() {
  const modal = document.getElementById("download-dialog");
  const closeButton = modal.querySelector('button:last-child');
  
  closeButton.addEventListener("click", () => modal.close());
  
  document.querySelectorAll(".modal-link").forEach((link) =>
    link.addEventListener("click", (e) => {
      e.preventDefault();
      modal.showModal();
    })
  );
}