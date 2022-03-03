function capitalizeFirstLetter(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

var GTMDatasetSearchSupport = function () {
  this.localStorageKeyname = "tempLocalStorage";
};

GTMDatasetSearchSupport.prototype.pushLinkToLocalStorage =
  function pushLinkToLocalStorage(link) {
    var data = $(link).data();
    console.log("What");
    try {
      var json = JSON.stringify(data);
      localStorage.setItem(this.localStorageKeyname, json);
      this.pushSearchResultClickEvent(data);
    } catch (e) {
      console.log("What");
      console.error(e);
    }
  };

GTMDatasetSearchSupport.prototype.pushSearchResultClickEvent =
  function pushSearchResultClickEvent(data) {
    console.log("sending pushSearchResultClickEvent ");
    if (typeof dataLayer == "undefined") return;
    console.log("sending pushSearchResultClickEvent ");
    dataLayer.push(data);
  };

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
