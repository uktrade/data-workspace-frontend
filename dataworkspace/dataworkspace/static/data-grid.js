function getCsrfToken() {
  if (document.getElementsByName('csrfmiddlewaretoken').length > 0) {
    return document.getElementsByName('csrfmiddlewaretoken')[0].value;
  }
  throw new Error('Unable to find CSRF token in the page');
}

function autoSizeColumns(columnApi) {
  var allColumnIds = [];
  columnApi.getAllColumns().forEach(function (column) {
    allColumnIds.push(column.colId);
  });
  columnApi.autoSizeColumns(allColumnIds, false);
}

function compareDates(filterDate, cellDate) {
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
  return '?' + Object.keys(obj).map(function(key) {
    return key + '=' +  encodeURIComponent(obj[key]);
  }).join('&');
}

function getBooleanFilterComponent() {
  function BooleanFilterComponent() {}

  BooleanFilterComponent.prototype.init = function (params) {
    this.eGui = document.createElement('div');
    this.eGui.className = 'ag-floating-filter-input';
    this.eGui.innerHTML = '<div class="ag-labeled ag-label-align-left ag-text-field ag-input-field">' +
      '<div class="ag-wrapper ag-input-wrapper ag-text-field-input-wrapper">' +
      '<select><option></option><option value="1">True</option><option value="0">False</option></select></div></div>';

    this.currentValue = null;
    this.eFilterInput = this.eGui.querySelector('select');
    this.eFilterInput.style.color = params.color;
    var that = this;

    function onSelectChanged() {
      if (that.eFilterInput.value === '') {
        params.parentFilterInstance(function (instance) {
          instance.onFloatingFilterChanged(null, null);
        });
        return;
      }

      that.currentValue = Number(that.eFilterInput.value);
      params.parentFilterInstance(function (instance) {
        instance.onFloatingFilterChanged('equals', that.currentValue);
      });
    }

    this.eFilterInput.addEventListener('input', onSelectChanged);

  };

  BooleanFilterComponent.prototype.onParentModelChanged = function (parentModel) {
    if (!parentModel) {
      this.eFilterInput.value = '';
      this.currentValue = null;
    } else {
      this.eFilterInput.value = parentModel.filter + '';
      this.currentValue = parentModel.filter;
    }
  };

  BooleanFilterComponent.prototype.getGui = function () {
    return this.eGui;
  };

  return BooleanFilterComponent;
}

function cleanFilters(filterModel, dataTypeMap) {
  var filters = filterModel != null ? filterModel : {};
  for (var key in filters) {
    if (dataTypeMap[key] != null && dataTypeMap[key] != filters[key].filterType) {
      filters[key].filterType = dataTypeMap[key];
    }
  }
  return filters;
}

function createInputFormField(name, value) {
  var field = document.createElement('input')
  field.setAttribute('name', name);
  field.setAttribute('value', value);
  return field;
}

function submitFilterForm(action, fileName, gridOptions, columnDataTypeMap) {
  var form = document.createElement('form');
    form.action = action
    form.method = 'POST';
    form.enctype = 'application/x-www-form-urlencoded';

    form.append(createInputFormField('csrfmiddlewaretoken', getCsrfToken()));
    if (fileName) {
      form.append(createInputFormField('export_file_name', fileName));
    }

    // Define the columns to include in the csv
    var displayedColumns = gridOptions.columnApi.getAllDisplayedColumns();
    for (var i = 0; i < displayedColumns.length; i++) {
      form.append(createInputFormField('columns', displayedColumns[i].colDef.field));
    }

    // Add current filters to the form
    var filters = cleanFilters(gridOptions.api.getFilterModel(), columnDataTypeMap);
    for (var key in filters) {
      form.append(createInputFormField('filters', JSON.stringify({[key]: filters[key]})));
    }

    // Add the current sort config to the form
    var sortModel = gridOptions.api.getSortModel()[0];
    if (sortModel) {
      form.append(createInputFormField('sortDir', sortModel.sort));
      form.append(createInputFormField('sortField', sortModel.colId));
    }

    // Add the form to the page, submit it and then remove it
    document.body.append(form);
    form.submit();
    form.remove();
}

function initDataGrid(columnConfig, dataEndpoint, downloadSegment, records, exportFileName, createChartEndpoint) {
  for (var i=0; i<columnConfig.length; i++) {
    var column = columnConfig[i];
    // Try to determine filter types from the column config.
    // Grid itself defaults to text if data type not set or not recognised
    if (column.dataType === 'numeric') {
      column.filter = 'agNumberColumnFilter';
    }
    else if (column.dataType === 'date') {
      column.filter = 'agDateColumnFilter';
    }
    else if (column.dataType === 'boolean') {
      column.floatingFilterComponent = 'booleanFloatingFilter';
      column.floatingFilterComponentParams = {
        suppressFilterButton: true
      };
    }
    else if (column.dataType === 'uuid') {
      column.filterParams = {
        filterOptions: ['equals', 'notEqual']
      };
    }
    else if (column.dataType === 'array') {
      column.filterParams = {
        filterOptions: ['contains', 'notContains', 'equals', 'notEqual']
      };
    }

    // Set comparator for date fields
    // (we do this here so it works for both client-side and server-side rendering)
    if (column.filter === 'agDateColumnFilter') {
      column.filterParams = {
        comparator: compareDates
      }
    }

    // Ensure ag-grid does not capitalise actual column names
    column.headerName = column.headerName ? column.headerName : column.field;
  }

  function suppressTabKey(params){
    var event = params.event;
    var key = event.key;
    if(key === "Tab") return true;
  }

  var gridOptions = {
    enableCellTextSelection: true,
    defaultColDef: {
      resizable: true,
      suppressMenu: true,
      floatingFilter: true,

      // suppressHeaderKeyboardEvent: function(params){
      // We don't suppress TAB from the header because we are showing floatingFilters
      // https://www.ag-grid.com/javascript-grid/floating-filters/ (the row with text boxes)
      // ag-grid doesn't suppress the tab navigation between these text boxes
      // this is either by design or a bug in ag-grid

      suppressKeyboardEvent: suppressTabKey,
      filterParams: {
        suppressAndOrCondition: true,
        buttons: ['reset']
      }
    },
    columnDefs: columnConfig,
    components: {
      loadingRenderer: function (params) {
        if (params.value !== null && params.value !== undefined) {
          return (params.valueFormatted != null && params.valueFormatted !== undefined) ? params.valueFormatted : params.value;
        }
        return '<img src="/__django_static/assets/images/loading.gif">';
      },
      booleanFloatingFilter: getBooleanFilterComponent(),
    }
  };

  var columnDataTypeMap = {};
  for (var i=0; i<gridOptions.columnDefs.length; i++) {
    columnDataTypeMap[gridOptions.columnDefs[i].field] = gridOptions.columnDefs[i].dataType;
  }

  if (dataEndpoint) {
    gridOptions.rowModelType = 'infinite';
    if (gridOptions.columnDefs.length > 0) {
      gridOptions.columnDefs[0].cellRenderer = 'loadingRenderer';
    }
  }
  else {
    gridOptions.rowData = records;
  }

  var gridContainer = document.querySelector('#data-grid');
  new agGrid.Grid(gridContainer, gridOptions);
  gridOptions.api.refreshView();
  autoSizeColumns(gridOptions.columnApi);

  if (dataEndpoint) {
    var initialDataLoaded = false;
    var dataSource = {
      rowCount: null,
      getRows: function (params) {
        var qs = {
          start: params.startRow,
          limit: params.endRow - params.startRow,
          filters: cleanFilters(params.filterModel, columnDataTypeMap)
        };
        if (params.sortModel[0]) {
          qs['sortField'] = params.sortModel[0].colId;
          qs['sortDir'] = params.sortModel[0].sort;
        }
        var xhr = new XMLHttpRequest();
        xhr.open('POST', dataEndpoint, true);
        xhr.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
        xhr.setRequestHeader("X-CSRFToken", getCsrfToken());
        xhr.onreadystatechange = function() {
          if (this.readyState === XMLHttpRequest.DONE) {
            if (this.status === 200) {
              var response = JSON.parse(xhr.responseText);
              params.successCallback(
                  response.records,
                  response.records.length < (params.endRow - params.startRow) ? (params.startRow + response.records.length) : -1
              );
              if (!initialDataLoaded) {
                autoSizeColumns(gridOptions.columnApi);
                initialDataLoaded = true;
              }
            }
            else {
              params.failCallback();
            }
          }
        }
        xhr.send(JSON.stringify(qs));
      }
    };
    gridOptions.api.setDatasource(dataSource);
  }

  var csvDownloadButton = document.querySelector('#data-grid-download');
  if (csvDownloadButton !== null) {
    csvDownloadButton.addEventListener('click', function (e) {
      if (dataEndpoint) {
        // Download a csv via the backend using current sort/filter options.
        submitFilterForm(dataEndpoint + downloadSegment, exportFileName, gridOptions, columnDataTypeMap)
      } else {
        // Download a csv locally using javascript
        gridOptions.api.exportDataAsCsv({
          fileName: exportFileName
        });
      }
      document.activeElement.blur();
      return;
    });

    var jsonDownloadButton = document.querySelector('#data-grid-json-download');
    if (jsonDownloadButton !== null) {
      jsonDownloadButton.addEventListener('click', function (e) {
        var rowData = [];
        gridOptions.api.forEachNodeAfterFilter(function (node) {
          rowData.push(node.data);
        });
        var dataStr = JSON.stringify({'data': rowData});
        var dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);

        var exportFileDefaultName = exportFileName.replace('csv', 'json');

        var linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        document.activeElement.blur();
        return;
      });
    }
  }

  var createChartButton = document.querySelector('#data-grid-create-chart');
  if (createChartButton !== null && createChartEndpoint) {
    createChartButton.addEventListener('click', function (e) {
      submitFilterForm(createChartEndpoint, null, gridOptions, columnDataTypeMap)
    });
  }

  document.querySelector('#data-grid-reset-filters').addEventListener('click', function(e){
    gridOptions.api.setFilterModel(null);
    document.activeElement.blur();
    return;
  });

  document.querySelector('#data-grid-reset-columns').addEventListener('click', function(e){
    gridOptions.columnApi.resetColumnState();
    document.activeElement.blur();
    return;
  });
}

window.initDataGrid = initDataGrid;
