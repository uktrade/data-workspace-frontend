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

class NewBooleanFilterComponent {
  init(params) {
    this.filterActive = false;
    this.currentValue = "";
    this.eGui = document.createElement("form");
    this.eGui.className = "ag-filter-wrapper ag-focus-managed";
    this.eGui.innerHTML =
      '<div class="ag-filter-body-wrapper ag-simple-filter-body-wrapper">' +
      '<div class="ag-picker-field ag-labeled ag-label-align-left ag-select ag-filter-select" role="presentation">' +
      '<div class="ag-wrapper ag-picker-field-wrapper" tabIndex="0" aria-expanded="false" role="listbox" aria-describedby="328-display" aria-label="Filtering operator">' +
      '<div class="ag-picker-field-display" id="328-display">Equals</div></div></div>' +
      '<div class="ag-picker-field ag-labeled ag-label-align-left ag-select ag-filter-select" role="presentation">' +
      '<select class="ag-wrapper ag-picker-field-wrapper"><option value="">Filter...</option><option value="1">True</option><option value="0">False</option></select></div></div>' +
      '<div class="ag-filter-apply-panel"><button type="button" class="ag-standard-button ag-filter-apply-panel-button">Reset</button></div>';
    this.eFilterInput = this.eGui.querySelector("select");
    this.eFilterReset = this.eGui.querySelector("button");
    this.filterChangedCallback = params.filterChangedCallback;
    this.eFilterInput.style.color = params.color;
    const that = this;
    this.eFilterInput.addEventListener("input", function (e) {
      const value = e.target.options[e.target.selectedIndex].value;
      if (value !== "") {
        that.filterActive = true;
        that.currentValue = Number(value);
        that.filterChangedCallback();
      } else {
        that.clearFilter();
      }
    });
    this.eFilterReset.addEventListener("click", function () {
      that.clearFilter();
    });
  }

  clearFilter() {
    if (!this.isFilterActive()) return;
    this.filterActive = false;
    this.currentValue = "";
    this.eFilterInput.value = this.currentValue;
    this.filterChangedCallback();
  }

  isFilterActive() {
    return this.filterActive;
  }

  getGui() {
    return this.eGui;
  }

  getModel() {
    if (!this.isFilterActive()) {
      return null;
    }
    return { filter: this.currentValue, type: "equals" };
  }

  setModel(model) {
    this.eFilterInput.value = model == null ? null : model.value;
  }
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

function getGridConfig() {
  const gridConfigScript = document.querySelector("#grid-config");
  return gridConfigScript !== null
    ? JSON.parse(gridConfigScript.textContent)
    : {};
}

function getSortField(columnApi) {
  const sort = columnApi.getColumnState().filter(function (c) {
    return c.sort != null;
  });
  if (sort.length > 0) {
    return [sort[0].colId, sort[0].sort];
  }
  return [null, null];
}
