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

function initDataGrid(columnConfig, dataEndpoint, records, exportFileName) {
  for (var i=0; i<columnConfig.length; i++) {
    var column = columnConfig[i];
    if (column.filter === 'agDateColumnFilter') {
      column.filterParams = {
        comparator: compareDates
      }
    }
  }
  var gridOptions = {
    defaultColDef: {
      resizable: true,
      suppressMenu: true,
      filterParams: {
        buttons: ['reset']
      }
    },
    columnDefs: columnConfig,
    rowData: records
  };
  var gridContainer = document.querySelector('#data-grid');
  new agGrid.Grid(gridContainer, gridOptions);
  gridOptions.api.refreshView();
  autoSizeColumns(gridOptions.columnApi);

  document.querySelector('#data-grid-download').addEventListener('click', function(e){
    gridOptions.api.exportDataAsCsv({
      fileName: exportFileName
    });
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
