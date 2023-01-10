function getCsrfToken() {
  if (document.getElementsByName("csrfmiddlewaretoken").length > 0) {
    return document.getElementsByName("csrfmiddlewaretoken")[0].value;
  }
  throw new Error("Unable to find CSRF token in the page");
}

function autoSizeColumns(columnApi) {
  var allColumnIds = [];
  columnApi.getAllColumns().forEach(function (column) {
    allColumnIds.push(column.colId);
  });
  columnApi.autoSizeColumns(allColumnIds, false);
}

function dateSortComparator(date1, date2) {
  if (date1 == null && date2 == null) return 0;
  if (date1 == null) return -1;
  if (date2 == null) return 1;
  return dayjs(date1) - dayjs(date2);
}

function htmlSortComparator(cell1, cell2) {
  var el1 = document.createElement("span");
  el1.innerHTML = cell1;
  var el2 = document.createElement("span");
  el2.innerHTML = cell2;
  return el1.innerText.localeCompare(el2.innerText);
}

function dateFilterComparator(filterDate, cellDate) {
  if (cellDate != null) {
    filterDate = dayjs(filterDate);
    cellDate = dayjs(cellDate);
    if (cellDate < filterDate) {
      return -1;
    } else if (cellDate > filterDate) {
      return 1;
    }
  }
  return 0;
}

function objectToQueryString(obj) {
  return (
    "?" +
    Object.keys(obj)
      .map(function (key) {
        return key + "=" + encodeURIComponent(obj[key]);
      })
      .join("&")
  );
}

function getBooleanFilterComponent() {
  function BooleanFilterComponent() {}

  BooleanFilterComponent.prototype.init = function (params) {
    this.eGui = document.createElement("div");
    this.eGui.className = "ag-floating-filter-input";
    this.eGui.innerHTML =
      '<div class="ag-labeled ag-label-align-left ag-text-field ag-input-field">' +
      '<div class="ag-wrapper ag-input-wrapper ag-text-field-input-wrapper">' +
      '<select><option></option><option value="1">True</option><option value="0">False</option></select></div></div>';

    this.currentValue = null;
    this.eFilterInput = this.eGui.querySelector("select");
    this.eFilterInput.style.color = params.color;
    var that = this;

    function onSelectChanged() {
      if (that.eFilterInput.value === "") {
        params.parentFilterInstance(function (instance) {
          instance.onFloatingFilterChanged(null, null);
        });
        return;
      }

      that.currentValue = Number(that.eFilterInput.value);
      params.parentFilterInstance(function (instance) {
        instance.onFloatingFilterChanged("equals", that.currentValue);
      });
    }

    this.eFilterInput.addEventListener("input", onSelectChanged);
  };

  BooleanFilterComponent.prototype.onParentModelChanged = function (
    parentModel
  ) {
    if (!parentModel) {
      this.eFilterInput.value = "";
      this.currentValue = null;
    } else {
      this.eFilterInput.value = parentModel.filter + "";
      this.currentValue = parentModel.filter;
    }
  };

  BooleanFilterComponent.prototype.getGui = function () {
    return this.eGui;
  };

  return BooleanFilterComponent;
}

// When the grid first loads or the page size
// is changed after load resize accordingly
function tableResize(tableEl, api) {
  if (tableEl.dataset.sizeToFit !== undefined) {
    api.sizeColumnsToFit();
  } else {
    autoSizeColumns(api);
  }
}

function getColumnsRemovedState() {
  let columnAPI = document.querySelector('#data-grid').gridOptions.columnApi
  return columnAPI.getAllColumns() !== columnAPI.getAllDisplayedColumns();
}

function getFilterState() {
  return document.querySelector('#data-grid').gridOptions.api.getFilterModel() !== {};
}
