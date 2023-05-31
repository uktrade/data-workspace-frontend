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
  referenceDataEndpoint,
) {
  var columnApi = gridOptions.columnApi;

  // Register download in event log
  if (referenceDataEndpoint) {
    let eventLogPOST = new XMLHttpRequest();
    eventLogPOST.open("POST", referenceDataEndpoint, true);
    eventLogPOST.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
    let eventLogData = JSON.stringify({"format": dataFormat})
    eventLogPOST.send(eventLogData);
  }

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
    rows_total: null,
    rows_downloaded: rowsDownLoaded,
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
  const sortFields = gridOptions.columnApi.getColumnState().filter(function(c) {
    return c.sort != null
  });
  if (sortFields.length > 0) {
    form.append(createInputFormField("sortDir", sortFields[0].sort));
    form.append(createInputFormField("sortField", sortFields[0].colId));
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
  eventLogEndpoint,
) {
  totalDownloadableRows =
    totalDownloadableRows != null ? totalDownloadableRows : 0;
  const userGridConfig = getGridConfig();
  for (var i = 0; i < columnConfig.length; i++) {
    var column = columnConfig[i];

    // Apply initial sort if available
    if (column.field === userGridConfig.sortColumn) {
      console.log(userGridConfig.sortDirection !== null ? userGridConfig.sortDirection : 'asc');
      column.sort = userGridConfig.sortDirection !== null ? userGridConfig.sortDirection : 'asc';
    }
    // Hide the column if it is not in the visible columns list for the user
    if (userGridConfig.visibleColumns != null) {
      column.initialHide = userGridConfig.visibleColumns.indexOf(column.field) === -1;
    }

    // Try to determine filter types from the column config.
    // Grid itself defaults to text if data type not set or not recognised
    if (column.dataType === "numeric") {
      column.filter = "agNumberColumnFilter";
    } else if (column.dataType === "date") {
      column.filter = "agDateColumnFilter";
    } else if (column.dataType === "boolean") {
      column.floatingFilterComponent = "booleanFloatingFilter";
      column.floatingFilterComponentParams = {
        suppressFilterButton: true,
      };
    } else if (column.dataType === "uuid") {
      column.filterParams = {
        filterOptions: ["equals", "notEqual"],
      };
    } else if (column.dataType === "array") {
      column.filterParams = {
        filterOptions: ["contains", "notContains", "equals", "notEqual"],
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
  }

  function suppressTabKey(params) {
    var event = params.event;
    var key = event.key;
    if (key === "Tab") return true;
  }

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

      suppressKeyboardEvent: suppressTabKey,
      filterParams: {
        suppressAndOrCondition: true,
        buttons: ["reset"],
      },
    },
    columnDefs: columnConfig,
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
      booleanFloatingFilter: getBooleanFilterComponent(),
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

  var gridContainer = document.querySelector("#data-grid");
  new agGrid.Grid(gridContainer, gridOptions);

  if (dataEndpoint) {
    var initialDataLoaded = false;
    var dataSource = {
      rowCount: null,
      getRows: function (params) {
        var qs = {
          start: params.startRow,
          limit: params.endRow - params.startRow,
          filters: cleanFilters(params.filterModel, columnDataTypeMap),
        };
        if (params.sortModel[0]) {
          qs["sortField"] = params.sortModel[0].colId;
          qs["sortDir"] = params.sortModel[0].sort;
        }
        var xhr = new XMLHttpRequest();
        var startTime = Date.now();
        var datasetPath = window.location.pathname
        var eventLogPOST = new XMLHttpRequest();
        xhr.open("POST", dataEndpoint, true);
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
        xhr.onreadystatechange = function () {
          if (this.readyState === XMLHttpRequest.DONE) {
            if (this.status === 200) {
              var response = JSON.parse(xhr.responseText);
              var rc = response.rowcount.count;
              totalDownloadableRows = response.rowcount.count;
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
                  dl_count.innerText =
                    "Download this data";
                }
              }
              if (rc <= downLoadLimit || (downLoadLimit == null && rc < 5000)) {
                if (rowcount) {
                  rowcount.innerText = rc.toLocaleString() + " rows";
                }
                if (dl_count) {
                  dl_count.innerText =
                    "Download this data";
                }
              }
              params.successCallback(
                response.records,
                response.records.length < params.endRow - params.startRow
                  ? params.startRow + response.records.length
                  : -1
              );
              if (!initialDataLoaded) {
                autoSizeColumns(gridOptions.columnApi);
                initialDataLoaded = true;
              }

              // log event in backend
              eventLogPOST.open("POST", eventLogEndpoint, true);
              eventLogPOST.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
              eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
              let eventLogData = JSON.stringify({
                "status_code": this.status,
                "query_time_milliseconds": Date.now() - startTime,
                "path": datasetPath
              })
              eventLogPOST.send(eventLogData);

            } else {
              gridOptions.overlayNoRowsTemplate =
                this.status === 504
                  ? "<p>The data you requested has taken too long to load. Please try again or contact the <a href='https://data.trade.gov.uk/support-and-feedback/'> Data Workspace team</a> if the problem continues.</p>"
                  : "<p>An unknown error occurred</p>";
              gridOptions.api.showNoRowsOverlay();

              // log event in backend
              eventLogPOST.open("POST", eventLogEndpoint, true);
              eventLogPOST.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
              eventLogPOST.setRequestHeader("X-CSRFToken", getCsrfToken());
              let eventLogData = JSON.stringify({
                "status_code": this.status,
                "query_time_milliseconds": Date.now() - startTime,
                "path": datasetPath
              })
              eventLogPOST.send(eventLogData);

              // hack to hide infinite spinner
              params.successCallback([], 0);
            }
          }
        };
        xhr.send(JSON.stringify(qs));
      },
    };

    // Apply any filers the user has saved
    if (userGridConfig.filters != null) {
      gridOptions.api.setFilterModel(userGridConfig.filters)
    }

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
      } else {
        // Download a csv locally using javascript
        gridOptions.api.exportDataAsCsv({
          fileName: exportFileName,
        });
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
        referenceDataEndpoint,
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
      });
      document.activeElement.blur();
      return;
    });
}

window.initDataGrid = initDataGrid;
