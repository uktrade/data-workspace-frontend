function cleanFilters(filterModel, dataTypeMap) {
  var filters = filterModel != null ? filterModel : {};
  for (var key in filters) {
    if (
      dataTypeMap[key] != null &&
      dataTypeMap[key] !== filters[key].filterType
    ) {
      filters[key].filterType = dataTypeMap[key];
    }
  }
  return filters;
}

function createInputFormField(name, value) {
  var field = document.createElement("input");
  field.setAttribute("name", name);
  field.setAttribute("value", value);
  return field;
}

function logDownloadEvent(
  gridOptions,
  itemId,
  itemName,
  itemType,
  dataFormat,
  rowsDownLoaded,
  referenceDataEndpoint
) {
  var columnApi = gridOptions.columnApi;

  // Register download in event log
  if (referenceDataEndpoint) {
    let eventLogPOST = new XMLHttpRequest();
    eventLogPOST.open("POST", referenceDataEndpoint, true);
    eventLogPOST.setRequestHeader(
      "Content-Type",
      "application/json;charset=UTF-8"
    );
    eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
    let eventLogData = JSON.stringify({ format: dataFormat });
    eventLogPOST.send(eventLogData);
  }

  let gridContainer = document.querySelector("#data-grid");
  const rowTotal = gridContainer.getAttribute("data-initial-row-count");

  // Google Analytics event
  if (window.dataLayer == null) return;
  window.dataLayer.push({
    event: "data_download",
    item_name: itemName,
    item_type: itemType,
    item_id: itemId,
    data_format: dataFormat,
    columns_total: columnApi.getColumns().length,
    columns_downloaded: columnApi.getAllDisplayedColumns().length,
    rows_total: rowTotal == null ? null : parseInt(rowTotal),
    rows_downloaded: rowsDownLoaded,
    table_name: gridContainer.getAttribute("data-source-name"),
  });
}

function submitFilterForm(action, fileName, gridOptions, columnDataTypeMap) {
  var form = document.createElement("form");
  form.action = action;
  form.method = "POST";
  form.enctype = "application/x-www-form-urlencoded";

  form.append(createInputFormField("csrfmiddlewaretoken", getCsrfToken()));
  if (fileName) {
    form.append(createInputFormField("export_file_name", fileName));
  }

  // Define the columns to include in the csv
  var displayedColumns = gridOptions.columnApi.getAllDisplayedColumns();
  for (var i = 0; i < displayedColumns.length; i++) {
    form.append(
      createInputFormField("columns", displayedColumns[i].colDef.field)
    );
  }

  // Add current filters to the form
  var filters = cleanFilters(
    gridOptions.api.getFilterModel(),
    columnDataTypeMap
  );
  for (var key in filters) {
    form.append(
      createInputFormField("filters", JSON.stringify({ [key]: filters[key] }))
    );
  }

  // Add the current sort config to the form
  const sort = getSortField(gridOptions.columnApi);
  if (sort[0] !== null) {
    form.append(createInputFormField("sortDir", sort[0]));
    form.append(createInputFormField("sortField", sort[1]));
  }

  // Add the form to the page, submit it and then remove it
  document.body.append(form);
  form.submit();
  form.remove();
}

function initDataGrid(
  columnConfig,
  dataEndpoint,
  downloadSegment,
  records,
  exportFileName,
  createChartEndpoint,
  referenceDataEndpoint,
  itemId,
  itemName,
  itemType,
  totalDownloadableRows,
  eventLogEndpoint
) {
  const gridContainer = document.querySelector("#data-grid");
  totalDownloadableRows =
    totalDownloadableRows != null ? totalDownloadableRows : 0;
  const userGridConfig = getGridConfig();
  let hasSavedConfig = Object.keys(userGridConfig).length > 0;
  const disableInteraction =
    gridContainer.getAttribute("data-disable-interaction") !== null;
  columnConfig.forEach(function (column, i) {
    column.originalPosition = i;
    column.position = i;
    if (hasSavedConfig) {
      const userColumnConfig = userGridConfig.columnDefs[column.field];
      if (userColumnConfig !== undefined) {
        column.sort = userColumnConfig.sort;
        column.initialHide = !userColumnConfig.visible;
        column.width = userColumnConfig.width;
        column.position = userColumnConfig.position;
      } else {
        column.initialHide = true;
        column.position = Object.keys(userGridConfig.columnDefs).length + i;
      }
    }

    if (disableInteraction) {
      column.filter = false;
      column.sortable = false;
    }
    // Try to determine filter types from the column config.
    // Grid itself defaults to text if data type not set or not recognised
    else if (column.dataType === "numeric") {
      column.filter = "agNumberColumnFilter";
    } else if (column.dataType === "date") {
      column.filter = "agDateColumnFilter";
    } else if (column.dataType === "boolean") {
      column.filter = NewBooleanFilterComponent;
    } else if (column.dataType === "uuid") {
      column.filterParams = {
        filterOptions: ["equals", "notEqual"],
      };
    } else if (column.dataType === "array") {
      column.filterParams = {
        filterOptions: [
          "contains",
          "notContains",
          "equals",
          "notEqual",
          "blank",
          "notBlank",
        ],
      };
    }

    // Set comparator for date fields
    // (we do this here so it works for both client-side and server-side rendering)
    if (column.filter === "agDateColumnFilter") {
      column.filterParams = {
        comparator: dateFilterComparator,
      };
    }

    // Ensure ag-grid does not capitalise actual column names
    column.headerName = column.headerName ? column.headerName : column.field;
  });

  var gridOptions = {
    enableCellTextSelection: true,
    suppressMenuHide: true,
    defaultColDef: {
      suppressSizeToFit: false,
      resizable: true,
      suppressMenu: false,
      floatingFilter: false,

      // suppressHeaderKeyboardEvent: function(params){
      // We don't suppress TAB from the header because we are showing floatingFilters
      // https://www.ag-grid.com/javascript-grid/floating-filters/ (the row with text boxes)
      // ag-grid doesn't suppress the tab navigation between these text boxes
      // this is either by design or a bug in ag-grid

      suppressKeyboardEvent: function (params) {
        var event = params.event;
        var key = event.key;
        if (key === "Tab") return true;
      },
      filterParams: {
        maxNumConditions: 1,
        buttons: ["reset"],
      },
    },
    columnDefs: columnConfig.sort(function (a, b) {
      return a.position - b.position;
    }),
    components: {
      loadingRenderer: function (params) {
        if (params.data != null) {
          return params.valueFormatted !== null &&
            params.valueFormatted !== undefined
            ? params.valueFormatted
            : params.value;
        }
        return '<img src="/__django_static/assets/images/loading.gif">';
      },
    },
  };

  var columnDataTypeMap = {};
  for (var i = 0; i < gridOptions.columnDefs.length; i++) {
    columnDataTypeMap[gridOptions.columnDefs[i].field] =
      gridOptions.columnDefs[i].dataType;
  }

  if (dataEndpoint) {
    gridOptions.rowModelType = "infinite";
    if (gridOptions.columnDefs.length > 0) {
      gridOptions.columnDefs[0].cellRenderer = "loadingRenderer";
    }
  } else {
    gridOptions.rowData = records;
  }

  new agGrid.Grid(gridContainer, gridOptions);

  // Apply any filers the user has saved
  if (userGridConfig.filters != null) {
    gridOptions.api.setFilterModel(userGridConfig.filters);
  }

  if (dataEndpoint) {
    let initialDataLoaded = false;
    const initialRowCount = gridContainer.getAttribute(
      "data-initial-row-count"
    );

    // When filters are reset, display the initial row count
    gridOptions.api.eventService.addEventListener("filterChanged", (e) => {
      if (
        initialDataLoaded &&
        initialRowCount !== null &&
        Object.keys(gridOptions.api.getFilterModel()).length === 0
      ) {
        const rowCount = parseInt(initialRowCount);
        document.getElementById("data-grid-rowcount").innerText =
          rowCount > 5000
            ? "Over " + Number("5000").toLocaleString() + " rows"
            : rowCount.toLocaleString() + " rows";
      }
    });

    var dataSource = {
      rowCount: initialRowCount,
      getRows: function (params) {
        var qs = {
          start: params.startRow,
          limit: params.endRow - params.startRow,
          filters: cleanFilters(params.filterModel, columnDataTypeMap),
        };
        const sort = getSortField(gridOptions.columnApi);
        if (sort[0] !== null) {
          qs["sortField"] = sort[0];
          qs["sortDir"] = sort[1];
        }
        var xhr = new XMLHttpRequest();
        var startTime = Date.now();
        var datasetPath = window.location.pathname;
        var eventLogPOST = new XMLHttpRequest();
        // Only fetch the row count if we don't already have it or if the filters are set
        let rowCountRequired = true;
        if (initialRowCount !== null && Object.keys(qs.filters).length === 0)
          rowCountRequired = false;

        if (rowCountRequired)
          document.getElementById("data-grid-rowcount").innerText =
            "Loading data...";

        xhr.open(
          "POST",
          dataEndpoint + (rowCountRequired ? "?count=1" : ""),
          true
        );
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
        xhr.onreadystatechange = function () {
          if (this.readyState === XMLHttpRequest.DONE) {
            if (this.status === 200) {
              const response = JSON.parse(xhr.responseText);
              const rc = response.rowcount.count;
              if (rc !== null) {
                totalDownloadableRows = rc;
                var downLoadLimit = response.download_limit;
                if (
                  downLoadLimit != null &&
                  totalDownloadableRows > downLoadLimit
                ) {
                  totalDownloadableRows = downLoadLimit;
                }
                const rowcount = document.getElementById("data-grid-rowcount");
                const dl_count = document.getElementById("data-grid-download");
                if (downLoadLimit == null && rc > 5000) {
                  if (rowcount) {
                    rowcount.innerText =
                      "Over " + Number("5000").toLocaleString() + " rows";
                  }
                  if (dl_count) {
                    dl_count.innerText = "Download this data";
                  }
                }
                if (downLoadLimit != null && rc > downLoadLimit) {
                  if (rowcount) {
                    rowcount.innerText =
                      "Over " + downLoadLimit.toLocaleString() + " rows";
                  }
                  if (dl_count) {
                    dl_count.innerText = "Download this data";
                  }
                }
                if (
                  rc <= downLoadLimit ||
                  (downLoadLimit == null && rc < 5000)
                ) {
                  if (rowcount) {
                    rowcount.innerText = rc.toLocaleString() + " rows";
                  }
                  if (dl_count) {
                    dl_count.innerText = "Download this data";
                  }
                }
              }
              params.successCallback(
                response.records,
                response.records.length < params.endRow - params.startRow
                  ? params.startRow + response.records.length
                  : -1
              );
              if (!initialDataLoaded && !hasSavedConfig) {
                autoSizeColumns(gridOptions.columnApi);
              }
              initialDataLoaded = true;

              // log event in backend
              eventLogPOST.open("POST", eventLogEndpoint, true);
              eventLogPOST.setRequestHeader(
                "Content-Type",
                "application/json;charset=UTF-8"
              );
              eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
              let eventLogData = JSON.stringify({
                status_code: this.status,
                query_time_milliseconds: Date.now() - startTime,
                path: datasetPath,
              });
              eventLogPOST.send(eventLogData);
            } else {
              gridOptions.overlayNoRowsTemplate =
                this.status === 504
                  ? "<p>The data you requested has taken too long to load. Please try again or contact the <a href='https://data.trade.gov.uk/support-and-feedback/'> Data Workspace team</a> if the problem continues.</p>"
                  : "<p>An unknown error occurred</p>";
              gridOptions.api.showNoRowsOverlay();

              // log event in backend
              eventLogPOST.open("POST", eventLogEndpoint, true);
              eventLogPOST.setRequestHeader(
                "Content-Type",
                "application/json;charset=UTF-8"
              );
              eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
              let eventLogData = JSON.stringify({
                status_code: this.status,
                query_time_milliseconds: Date.now() - startTime,
                path: datasetPath,
              });
              eventLogPOST.send(eventLogData);

              // hack to hide infinite spinner
              params.successCallback([], 0);
            }
          }
        };
        xhr.send(JSON.stringify(qs));
      },
    };

    gridOptions.api.setDatasource(dataSource);
  }

  var csvDownloadButton = document.querySelector("#data-grid-download");
  if (csvDownloadButton !== null) {
    csvDownloadButton.addEventListener("click", function (e) {
      if (dataEndpoint) {
        // Download a csv via the backend using current sort/filter options.
        submitFilterForm(
          dataEndpoint + downloadSegment,
          exportFileName,
          gridOptions,
          columnDataTypeMap
        );
        document.getElementById("popup").close();
      } else {
        // Download a csv locally using javascript
        gridOptions.api.exportDataAsCsv({
          fileName: exportFileName,
        });
        document.getElementById("popup").close();
      }
      logDownloadEvent(
        gridOptions,
        itemId,
        itemName,
        itemType,
        "CSV",
        dataEndpoint == null
          ? gridOptions.api.getDisplayedRowCount()
          : totalDownloadableRows,
        referenceDataEndpoint
      );
      document.activeElement.blur();
      return;
    });

    var jsonDownloadButton = document.querySelector("#data-grid-json-download");
    if (jsonDownloadButton !== null) {
      jsonDownloadButton.addEventListener("click", function (e) {
        var rowData = [];
        gridOptions.api.forEachNodeAfterFilter(function (node) {
          rowData.push(node.data);
        });
        var dataStr = JSON.stringify({ data: rowData });
        var dataUri =
          "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);

        var exportFileDefaultName = exportFileName.replace("csv", "json");

        var linkElement = document.createElement("a");
        linkElement.setAttribute("href", dataUri);
        linkElement.setAttribute("download", exportFileDefaultName);
        linkElement.click();
        document.getElementById("popup").close();
        logDownloadEvent(
          gridOptions,
          itemId,
          itemName,
          itemType,
          "JSON",
          dataEndpoint == null
            ? gridOptions.api.getDisplayedRowCount()
            : totalDownloadableRows,
          referenceDataEndpoint
        );
        document.activeElement.blur();
        return;
      });
    }
  }

  var createChartButton = document.querySelector("#data-grid-create-chart");
  if (createChartButton !== null && createChartEndpoint) {
    createChartButton.addEventListener("click", function (e) {
      submitFilterForm(
        createChartEndpoint,
        null,
        gridOptions,
        columnDataTypeMap
      );
    });
  }

  document
    .querySelector("#data-grid-reset-view")
    .addEventListener("click", function (e) {
      gridOptions.api.setFilterModel(null);
      gridOptions.columnApi.resetColumnState();
      // Unset the saved column config
      gridOptions.columnApi.getColumns().forEach((c) => {
        gridOptions.columnApi.setColumnVisible(c.getColId(), true);
        gridOptions.columnApi.moveColumn(
          c.getColId(),
          c.colDef.originalPosition
        );
        gridOptions.columnApi.applyColumnState({
          defaultState: { sort: null },
        });
      });
      document.activeElement.blur();
      if (hasSavedConfig) {
        const button = e.currentTarget;
        button.innerHTML = "Resetting view";
        button.setAttribute("disabled", "disabled");
        var xhr = new XMLHttpRequest();
        xhr.open(
          "DELETE",
          gridContainer.getAttribute("data-save-view-url"),
          true
        );
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
        xhr.onreadystatechange = function () {
          if (this.readyState === XMLHttpRequest.DONE) {
            button.innerHTML = "Reset view";
            button.removeAttribute("disabled");
            hasSavedConfig = false;
          }
        };
        xhr.send();
      }
    });

  var saveViewButton = document.querySelector("#data-grid-save-view");
  if (saveViewButton !== null) {
    saveViewButton.addEventListener("click", function (e) {
      saveViewButton.innerHTML = "Saving view";
      saveViewButton.setAttribute("disabled", "disabled");
      const columnState = Object.fromEntries(
        gridOptions.columnApi.getColumnState().map(function (c, i) {
          c.position = i;
          return [c.colId, c];
        })
      );
      let gridConfig = {
        filters: gridOptions.api.getFilterModel(),
        columnDefs: gridOptions.columnApi.getColumns().map(function (c, i) {
          const colState = columnState[c.colId];
          return {
            field: c.colId,
            position: colState.position,
            visible: c.visible,
            width: colState.width,
            sort: c.sort,
          };
        }),
      };
      var xhr = new XMLHttpRequest();
      xhr.open("POST", gridContainer.getAttribute("data-save-view-url"), true);
      xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
      xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
      xhr.onreadystatechange = function () {
        if (this.readyState === XMLHttpRequest.DONE) {
          if (this.status === 200) {
            document
              .getElementById("grid-saved-banner")
              .classList.remove("govuk-visually-hidden");
          }
          saveViewButton.innerHTML = "Save view";
          saveViewButton.removeAttribute("disabled");
          hasSavedConfig = true;
        }
      };
      xhr.send(JSON.stringify(gridConfig));
    });
    document
      .getElementById("dismiss-banner")
      .addEventListener("click", function (e) {
        e.preventDefault();
        document
          .getElementById("grid-saved-banner")
          .classList.add("govuk-visually-hidden");
      });
  }
}

var increaseGridButton = document.querySelector("#increase-grid-button");
if (increaseGridButton !== null) {
  increaseGridButton.addEventListener("click", function (e) {
    document
      .getElementById("collapsible-header")
      .classList.toggle("govuk-visually-hidden");
    if (increaseGridButton.innerText === "Show more rows") {
      increaseGridButton.innerText = "Show less rows";
    } else {
      increaseGridButton.innerText = "Show more rows";
    }
    document.getElementById("data-grid").classList.toggle("grid-maximised");
    document
      .getElementsByClassName("app-compressed-grid")[0]
      .classList.toggle("remove-border");
  });
}

document.addEventListener("DOMContentLoaded", function () {
  document
    .getElementById("downloadData")
    .addEventListener("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      document.getElementById("popup").showModal();
    });

  document.getElementById("closePopUp").addEventListener("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    document.getElementById("popup").close();
  });
});

window.initDataGrid = initDataGrid;
