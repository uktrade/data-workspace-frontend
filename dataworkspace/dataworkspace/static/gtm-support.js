function capitalizeFirstLetter(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

var GTMDatasetSearchSupport = function () {};

GTMDatasetSearchSupport.prototype.pushSearchEvent = function pushSearchEvent() {
  if (typeof dataLayer !== "undefined") {
    var update = {
      event: "filter",
      searchTerms: document.getElementById("search").value,
      resultsReturned: parseInt(
        document.getElementById("search-results-count").textContent
      ),
    };

    $("#live-search-form fieldset").map(function () {
      var labels = [];
      var filterId = $(this).attr("id").replace(/^id_/, "");
      $(this)
        .find("input[type=checkbox]:checked")
        .map(function () {
          // the filter checkboxes have the number of results in brackets
          // e.g. "Filter (1)"
          // We remove the brackets and the number before sending to dataLayer
          var labelText = $("label[for='" + $(this).attr("id") + "']").text();
          var cleanText = labelText.replaceAll(/\([0-9]+\)/g, "");
          labels.push(cleanText.trim());
        });

      update["filterData" + capitalizeFirstLetter(filterId)] = labels
        .sort()
        .join(";");
    });

    dataLayer.push(update);
  }
};
