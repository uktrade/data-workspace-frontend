document.addEventListener("DOMContentLoaded", function () {
  const esdaFieldCheckBox = document.getElementById("id_esda");
  if (esdaFieldCheckBox) {
    esdaFieldCheckBox.addEventListener("change", function (event) {
      if (
        confirm(
          `Please confirm that you want to set ESDA to ${event.target.checked}.`
        )
      ) {
        event.target.dataset.esda = event.target.checked;
      } else {
        event.preventDefault();
        event.target.checked = !event.target.checked;
      }
    });
  }
});
