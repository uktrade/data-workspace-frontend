("use strict");

var ToggleInputClassOnFocus = function ($el) {
  var $toggleTarget = $el.find(".js-class-toggle");

  if (!inputIsEmpty()) {
    addFocusClass();
  }

  $toggleTarget.on("focus", addFocusClass);
  $toggleTarget.on("blur", removeFocusClassFromEmptyInput);

  function inputIsEmpty() {
    return $toggleTarget.val() === "";
  }

  function addFocusClass() {
    $toggleTarget.addClass("focus");
  }

  function removeFocusClassFromEmptyInput() {
    if (inputIsEmpty()) {
      $toggleTarget.removeClass("focus");
    }
  }
};

var LiveSearch = function (formSelector, wrapperSelector, GTM, linkSelector, GOVUKFrontend) {

  this.GOVUKFrontend = GOVUKFrontend;

  this.wrapperSelector = wrapperSelector;
  this.$wrapper = $(wrapperSelector);
  this.$form = $(formSelector);

  this.state = false;
  this.previousState = false;
  this.resultsCache = {};
  this.GTM = GTM;

  this.originalState = this.$form.serializeArray();
  this.saveState();

  var self = this;

  this.$wrapper.on("click", linkSelector, function (e) {
    self.GTM.pushSearchResultClick(e.target);
  });

  this.$form.on(
    "change",
    "input[type=checkbox], select",
    this.formChange.bind(this)
  );
  this.$form.on("search", "input[type=search]", this.formChange.bind(this));
  $(window).on("popstate", this.popState.bind(this));

  this.$form.find("input[type=submit]").click(
    function (e) {
      this.formChange();
      e.preventDefault();
    }.bind(this)
  );

  this.$form.find("input[type=search]").keypress(
    function (e) {
      if (e.keyCode == 13) {
        // 13 is the return key
        this.formChange();
        e.preventDefault();
      }
    }.bind(this)
  );

  this.$form.find("select").change(
    function (e) {
      this.formChange();
      e.preventDefault();
    }.bind(this)
  );

  this.bindFilterButtons();
};

LiveSearch.prototype.saveState = function saveState(state) {
  if (typeof state === "undefined") {
    state = this.$form.serializeArray();
  }
  this.previousState = this.state;
  this.state = state;
};

LiveSearch.prototype.popState = function popState(event) {
  if (event.originalEvent.state) {
    this.saveState(event.originalEvent.state);
  } else {
    this.saveState(this.originalState);
  }

  this.restoreBooleans();
  this.restoreSearchInputs();
  this.restoreSortSelect();
  this.updateResults();
};

LiveSearch.prototype.formChange = function formChange(e) {
  var pageUpdated;
  if (this.isNewState()) {
    this.saveState();
    pageUpdated = this.updateResults();
    pageUpdated.done(
      function () {
        if (typeof this.GTM !== "undefined") {
          try {
            this.GTM.pushSearchEvent();
          } catch(e){
            console.error(e);
          }
        }

        var newPath =
          window.location.origin +
          this.$form.attr("action") +
          "?" +
          $.param(this.state);
        history.pushState(this.state, "", newPath);
      }.bind(this)
    );
  }
};

LiveSearch.prototype.cache = function cache(slug, data) {
  if (typeof data === "undefined") {
    return this.resultsCache[slug];
  } else {
    this.resultsCache[slug] = data;
  }
};

LiveSearch.prototype.isNewState = function isNewState() {
  return $.param(this.state) !== this.$form.serialize();
};

LiveSearch.prototype.updateResults = function updateResults() {
  this.showLoadingIndicators();

  var self = this;
  var searchState = $.param(this.state);
  var liveState = this.$form.serializeArray();
  var cachedResultData = this.cache(searchState);

  if (typeof cachedResultData === "undefined") {
    return $.ajax({
      url: this.$form.attr("action"),
      data: $.param(liveState),
      searchState: searchState,
    })
      .done(function (response) {
        self.cache(this.searchState, response);
        self.displayFilterResults(response, this.searchState);
      })
      .fail(function (response) {
        self.showErrorIndicator();
      });
  } else {
    this.displayFilterResults(cachedResultData, searchState);
    var out = new $.Deferred();
    return out.resolve();
  }
};

LiveSearch.prototype.showLoadingIndicators = function showLoadingIndicators() {
  this.$wrapper.css("opacity", "0.25");
};

LiveSearch.prototype.showErrorIndicator = function showErrorIndicator() {
  this.$wrapper.css("opacity", "1");
  this.$wrapper.text(
    "Error. Please try modifying your search and trying again."
  );
};

LiveSearch.prototype.bindFilterButtons = function bindFilterButtons() {
  var buttonSelector = "button[data-module=remove-filter]";
  var self = this;
  this.$wrapper.on("click", buttonSelector, function (e) {

    var $button = $(e.target);
    var data = $button.data();

    // Find the checkbox corresponding to this button
    var checkboxSelector = "input[type=checkbox][name=" + data.filterType + "][value=" + data.id + "]";

    $(checkboxSelector).prop("checked", false);
    $button.prop("disabled", true);
    self.$form.submit();
  })

}

LiveSearch.prototype.displayFilterResults = function displayFilterResults(
  response,
  state
) {
  if (state == $.param(this.state) && state !== "") {
    this.replaceBlock(
      this.wrapperSelector,
      $(response).find(this.wrapperSelector).html()
    );
  }

  this.$wrapper.css("opacity", "1");

  if (window.installFilterShowMore !== undefined) {
    // Hook into app-filter-show-more-v2.js to un-hide the "show more" button on search filters.
    window.installFilterShowMore();
  }

  if (typeof window.installFilterTextSearch === "function") {
    window.installFilterTextSearch();
  }

  // Rebind govuk events
  var wrapperElement = $(this.wrapperSelector).get(0);
  this.GOVUKFrontend.initAll({scope: wrapperElement});

  this.bindFilterButtons();

};


LiveSearch.prototype.replaceBlock = function replaceBlock(selector, html) {
  var currentActiveElement = document.activeElement
    ? document.activeElement.id
    : null;
  $(selector).html(html);
  if (
    currentActiveElement !== null &&
    document.getElementById(currentActiveElement) !== null
  ) {
    document.getElementById(currentActiveElement).focus();
  }
};

LiveSearch.prototype.restoreBooleans = function restoreBooleans() {
  var that = this;
  this.$form
    .find("input[type=checkbox], input[type=radio]")
    .each(function (i, el) {
      var $el = $(el);
      $el.prop(
        "checked",
        that.isBooleanSelected($el.attr("name"), $el.attr("value"))
      );
    });
};

LiveSearch.prototype.isBooleanSelected = function isBooleanSelected(
  name,
  value
) {
  var i, _i;
  for (i = 0, _i = this.state.length; i < _i; i++) {
    if (this.state[i].name === name && this.state[i].value === value) {
      return true;
    }
  }
  return false;
};

LiveSearch.prototype.restoreSearchInputs = function restoreSearchInputs() {
  var that = this;
  this.$form.find("input[type=search]").each(function (i, el) {
    var $el = $(el);
    $el.val(that.getTextInputValue($el.attr("name")));
  });
};

LiveSearch.prototype.restoreSortSelect = function restoreSortSelect() {
  var that = this;
  this.$form.find("select").each(function (i, el) {
    var $el = $(el);
    $el.val(that.getTextInputValue($el.attr("name")));
  });
};

LiveSearch.prototype.getTextInputValue = function getTextInputValue(name) {
  var i, _i;
  for (i = 0, _i = this.state.length; i < _i; i++) {
    if (this.state[i].name === name) {
      return this.state[i].value;
    }
  }
  return "";
};

function attachTextFilter($text) {
  var targetId = $($text).attr("data-target");
  var target = $("#" + targetId);

  var $items = $(".search-target", target);

  function filterOn(value) {
    $($items).each(function (i, e) {
      var searchText = $(e).attr("data-item-seach-text");
      if (searchText.indexOf(value) >= 0) {
        $(e).show();
      } else {
        $(e).hide();
      }
    });
  }

  $($text)
    .on("keyup", function () {
      var value = $(this).val().toLocaleLowerCase();
      filterOn(value);
    })
    .on("search", function () {
      var value = $(this).val().toLocaleLowerCase();
      filterOn(value);
    });
}

function installFilterTextSearch() {
  $("[data-module='filter-search']").each(function (i, e) {
    attachTextFilter(e);
  });
}

installFilterTextSearch();

// Simple queue to make sure earlier clicks are not processed
// after later ones, which would cause the state in the browser
// to not match the server
let queue = Promise.resolve();

document.body.addEventListener('click', function(event) {
  const toggle = event.target.closest('.bookmark-toggle');
  if (!toggle) return;

  const dataset_id = toggle.getAttribute('data-dataset-id');
  const csrf = document.getElementsByName("csrfmiddlewaretoken")[0].value;
  const [classFunc, path, title] = toggle.classList.contains('is-bookmarked') ?
    ['remove', '/datasets/' + dataset_id + '/unset-bookmark', 'You have not bookmarked this dataset'] :
    ['add', '/datasets/' + dataset_id + '/set-bookmark', 'You have bookmarked this dataset'];

  toggle.classList[classFunc]('is-bookmarked');
  toggle.setAttribute('title', title);
  queue = queue.finally(() => fetch(
    path, {
      method: 'POST',
      headers: {'Content-Type': 'text/plain;charset=UTF-8"', 'X-CSRFToken': csrf
    }}
  ));
});