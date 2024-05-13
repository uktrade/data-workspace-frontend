document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener("click", function (e) {
        if (e.target.name === "select_all") {
            var datasetCheckboxes = document.getElementsByName("dataset_id");
            
            for (var index = 0; index < datasetCheckboxes.length; index++) {
                datasetCheckboxes[index].checked = e.target.checked;
            }
        }
    });
});