;
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
};

var GTMDatasetSearchSupport = function() {};

GTMDatasetSearchSupport.prototype.pushSearchEvent = function pushSearchEvent() {
    if (typeof(dataLayer) !== 'undefined') {
        var update = {
            "event": "filter",
            "searchTerms": document.getElementById('search').value,
            "resultsReturned": parseInt(document.getElementById('search-results-count').textContent),
        };

        $("#live-search-form fieldset").map(
            function () {
                labels = [];
                filter_id = $(this).attr('id').replace(/^id_/, "")
                $(this).find('input[type=checkbox]:checked').map(
                    function () {
                        labels.push($("label[for='" + $(this).attr('id') + "']").text().trim());
                    }
                );
                update['filterData' + capitalizeFirstLetter(filter_id)] = labels.sort().join(';')
            }
        )

        dataLayer.push(update);
    }
};
;
