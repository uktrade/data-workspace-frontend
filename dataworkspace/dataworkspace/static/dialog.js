document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("download-dialog");
  if (modal) {
    const closeButton = modal.querySelector('button:last-child');
    
    closeButton.addEventListener("click", () => modal.close());
    
    document.querySelectorAll(".modal-link").forEach((link) =>
      link.addEventListener("click", (e) => {
        e.preventDefault();
        modal.showModal();
      })
    );
  }
});