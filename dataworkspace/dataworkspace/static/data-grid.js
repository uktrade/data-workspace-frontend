function getCookie(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
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
function initDataGrid(columnConfig, dataEndpoint, records, exportFileName) {
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
        filterOptions: ['equals', 'notEquals']
      };
    }

    // Set comparator for date fields
    // (we do this here so it works for both client-side and server-side rendering)
    if (column.filter === 'agDateColumnFilter') {
      column.filterParams = {
        comparator: compareDates
      }
    }
  }

  var gridOptions = {
    enableCellTextSelection: true,
    defaultColDef: {
      resizable: true,
      suppressMenu: true,
      floatingFilter: true,
      filterParams: {
        suppressAndOrCondition: true,
        buttons: ['reset']
      }
    },
    columnDefs: columnConfig,
    components: {
      loadingRenderer: function (params) {
        return params.value !== undefined ? params.value : '<img src="/__django_static/assets/images/loading.gif">';
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
    gridOptions.columnDefs[0].cellRenderer = 'loadingRenderer';
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
        xhr.setRequestHeader("X-CSRFToken", getCookie('data_workspace_csrf'));
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

  document.querySelector('#data-grid-download').addEventListener('click', function (e) {
    if (dataEndpoint) {
      // Download a csv via the backend using current sort/filter options.
      var form = document.createElement('form');
      form.action = dataEndpoint + '?download=1'
      form.method = 'POST';
      form.enctype = 'application/x-www-form-urlencoded';

      form.append(createInputFormField('csrfmiddlewaretoken', getCookie('data_workspace_csrf')));
      form.append(createInputFormField('export_file_name', exportFileName));

      // Define the columns to include in the csv
      var displayedColumns = gridOptions.columnApi.getAllDisplayedColumns();
      for (var i=0; i<displayedColumns.length; i++) {
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
    else {
      // Download a csv locally using javascript
      gridOptions.api.exportDataAsCsv({
        fileName: exportFileName
      });
    }
    document.activeElement.blur();
    return;
  });

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
